from datetime import timedelta
from django.utils import timezone
from rest_framework.exceptions import ValidationError
from django.db import transaction
from users.constants import create_activity_log, create_notification
from users.errors.exceptions import (
    InvalidStatusError,
    PermissionDeniedError,
    TaskAlreadyAssigned,
    TechnicalReportMissingError,
)
from users.models import ActivityLog, Notification, ProjectRole, RequestForm, Task, TaskDependency, TechnicalReportForm, User
from users.services import UserAvailabilityService
from users.services.invitationsService import InvitationService

TASK_TRANSITIONS = {
        "TODO": ["INPROGRESS"],
        "INPROGRESS": ["REVIEW", "TODO"],
        "REVIEW": ["DONE"],
        "DONE": []
}
def can_change_status(user, task):
        is_assignee = task.assigned_to_id == user.id

        is_manager = ProjectRole.objects.filter(
            project=task.project,
            user=user,
            role__in=["ADMIN", "MANAGER"],
        ).exists()

        return is_assignee or is_manager
def validate_review_transition(task):
        report = TechnicalReportForm.objects.filter(
            task=task,
            user=task.assigned_to,
            status="SUBMITTED",
        ).order_by("-created_at").first()

        if not report:
            raise TechnicalReportMissingError()

        return report
def handle_side_effects(task, user, new_status):
        if new_status == "INPROGRESS" and not task.start_time:
            task.start_time = timezone.now()

        if new_status == "DONE":
            task.end_time = timezone.now()
            if task.start_time:
                task.actual_duration = task.end_time - task.start_time






def validate_employee_task_availability(
        *,
        employee,
        due_date,
        expected_duration,
        actual_duration=None,
    ):
        if due_date is None or expected_duration is None:
            return

        actual_duration = actual_duration or timedelta(0)
        remaining_duration = max(
            expected_duration - actual_duration,
            timedelta(0),
        )

        approved_leaves = RequestForm.objects.filter(
            user=employee,
            request_type="LEAVE",
            status="APPROVED",
            leave_end__gte=timezone.now(),
        ).order_by("leave_start")

        now = timezone.now()

        for leave in approved_leaves:
            if leave.leave_start <= now <= leave.leave_end:
                raise ValidationError({
                    "assigned_to": (
                        "This employee is currently on approved leave "
                        "and cannot receive new tasks."
                    )
                })

            effective_deadline = min(
                due_date,
                leave.leave_start,
            )

            available_duration = effective_deadline - now

            if due_date >= leave.leave_start and remaining_duration > available_duration:
                raise ValidationError({
                    "assigned_to": (
                        "This employee cannot complete the task before "
                        "the approved leave starts."
                    )
                })


class TaskService:

    @staticmethod
    @transaction.atomic
    def soft_delete_task(*,task, user):

        is_project_manager = ProjectRole.objects.filter(
            project=task.project,
            user=user,
            role__in=["ADMIN", "MANAGER"],
        ).exists()

        is_workspace_owner = (
            task.project.workspace.creator_id == user.id
        )

        if not is_project_manager and not is_workspace_owner:
            raise PermissionDeniedError()



        if task.is_deleted:
            return task
        dependent_relations = (
                task.dependent_tasks
                .select_related("successor")
                .filter(successor__is_deleted=False)
            )

        if dependent_relations.exists():
                raise ValidationError({
                    "detail": (
                        "This task cannot be deleted because "
                        "other active tasks depend on it."
                    ),
                    "code": "TASK_HAS_DEPENDENTS",
                    "dependent_tasks": [
                        {
                            "dependency_id": relation.id,
                            "task_id": relation.successor_id,
                            "title": relation.successor.title,
                            "status": relation.successor.status,
                        }
                        for relation in dependent_relations
                    ],
                })

        # task.task_dependencies.all().delete()
        task.is_deleted = True
        task.deleted_at = timezone.now()
        task.deleted_by = user

        task.save(
            update_fields=[
                "is_deleted",
                "deleted_at",
                "deleted_by",
                "updated_at",
            ]
        )
        TaskService.refresh_project_status(
            task.project,
        )

        create_activity_log(
            user=user,
            action="TASK_DELETED",
            action_id=task.id,
            changes={
                "subject_name": user.username,
                "target_title": task.title,
                "reason": (
                    f"Task '{task.title}' was soft deleted "
                    f"by {user.username}."
                ),
                "is_by_admin": True,
            },
        )

        return task


    @staticmethod
    def claim_task(task, user):
        if task.assigned_to is not None:
            raise TaskAlreadyAssigned()

        is_project_member = ProjectRole.objects.filter(project=task.project, user=user).exists()
        if not is_project_member:
            raise PermissionDeniedError()

        task.assigned_to = user
        task.status = "TODO"
        task.save(update_fields=["assigned_to", "status", "updated_at"])

        managers = User.objects.filter(
            projectrole__project=task.project,
            projectrole__role__in=['ADMIN', 'MANAGER'],
        ).exclude(id=user.id).distinct()

        for manager in managers:
            create_notification(
                recipient=manager,
                notification_type="SYSTEM_ALERT",
                title="تم استلام مهمة",
                message=f"قام الموظف {user.username} باستلام المهمة: {task.title}",
                navigation_target=f"/tasks/{task.id}",
            )

        create_activity_log(
            user=user,
            action="GENERAL_UPDATE",
            action_id=task.id,
            subject_name=user.username,
            target_title=task.title,
            reason="Task claimed by employee",
            is_by_admin=False,
        )

        return task

    from django.db import transaction
    from rest_framework.exceptions import ValidationError


    @staticmethod
    def create_task(
            *,
            user,
            serializer,
        ):
            validated_data = serializer.validated_data.copy()

            dependency_tasks = validated_data.pop(
                "dependency_ids",
                [],
            )

            assigned_user = validated_data.get("assigned_to")
            project = validated_data.get("project")
            due_date = validated_data.get("due_date")
            expected_duration = validated_data.get("expected_duration")
            actual_duration = validated_data.get("actual_duration")

            if project is None:
                raise ValidationError({
                    "project": "Project is required."
                })

            if assigned_user is not None:
                UserAvailabilityService.ensure_active(
                    assigned_user,
                    action="task assignment",
                )
                validate_employee_task_availability(
                    employee=assigned_user,
                    due_date=due_date,
                    expected_duration=expected_duration,
                    actual_duration=actual_duration,
                )
            task = Task.objects.create(
                creator=user,
                status="TODO",
                assignment_state=(
                    "ASSIGNED"
                    if assigned_user is not None
                    else "UNASSIGNED_NEW"
                ),
                **validated_data,)

            TaskService.create_dependencies(
                task=task,
                dependency_tasks=dependency_tasks,
                created_by=user,
            )


            if assigned_user is not None:
                is_project_member = ProjectRole.objects.filter(
                    project=project,
                    user=assigned_user,
                ).exists()

                if not is_project_member:
                    InvitationService.send_project_invitation(
                        sender=user,
                        data={
                            "project_id": project.id,
                            "receiver_emails": [
                                assigned_user.email
                            ],
                            "role": "EMPLOYEE",
                        },
                    )

            create_activity_log(
                user=user,
                action="GENERAL_UPDATE",
                action_id=task.id,
                subject_name=user.username,
                target_title=task.title,
                reason="Task created",
                is_by_admin=True,
            )
            TaskService.refresh_project_status(
                    project,
                )

            return task


    @staticmethod
    def creates_circular_dependency(*, predecessor, successor):
        visited = set()
        stack = [successor]

        while stack:
            current_task = stack.pop()

            if current_task.id == predecessor.id:
                return True

            if current_task.id in visited:
                continue

            visited.add(current_task.id)

            successor_ids = TaskDependency.objects.filter(
                predecessor=current_task,
                successor__is_deleted=False,
            ).values_list(
                "successor_id",
                flat=True,
            )

            stack.extend(
                Task.objects.filter(id__in=successor_ids)
            )

        return False
    @staticmethod
    def create_dependencies(
        *,
        task,
        dependency_tasks,
        created_by,
    ):
        if not dependency_tasks:
            return []

        dependencies = []
        predecessor_ids = set()

        for predecessor in dependency_tasks:
            if predecessor.id in predecessor_ids:
                raise ValidationError({
                    "dependency_ids": (
                        f"Task {predecessor.id} was selected "
                        "more than once."
                    )
                })

            predecessor_ids.add(predecessor.id)

            if predecessor.id == task.id:
                raise ValidationError({
                    "dependency_ids": (
                        "A task cannot depend on itself."
                    )
                })

            if predecessor.project_id != task.project_id:
                raise ValidationError({
                    "dependency_ids": (
                        "All dependency tasks must belong "
                        "to the same project."
                    )
                })
            if TaskService.creates_circular_dependency(
                predecessor=predecessor,
                successor=task,
            ):
                raise ValidationError({
                    "detail": (
                        "This dependency cannot be created because "
                        "it would cause a circular dependency."
                    ),
                    "code": "CIRCULAR_DEPENDENCY",
                    "dependency": {
                        "predecessor_id": predecessor.id,
                        "predecessor_title": predecessor.title,
                        "successor_id": task.id,
                        "successor_title": task.title,
                    },
                })

            dependencies.append(
                TaskDependency(
                    predecessor=predecessor,
                    successor=task,
                    dependency_type="BLOCKS",
                    created_by=created_by,
                )
            )

        return TaskDependency.objects.bulk_create(
            dependencies
        )

    """
    @staticmethod
    def update_status(task, user, status_value):

        allowed = TASK_TRANSITIONS.get(task.status, [])
        if status_value not in allowed:
            raise InvalidStatusError()

        if not can_change_status(user, task):
            raise PermissionDeniedError()

        if status_value == "REVIEW":
            validate_review_transition(task)

            managers = User.objects.filter(
                projectrole__project=task.project,
                projectrole__role__in=["ADMIN", "MANAGER"],
            ).distinct()

            for manager in managers:
                create_notification(
                    recipient=manager,
                    notification_type="REPORT_SUBMITTED",
                    title="New Technical Report Submitted",
                    message=f"Employee {user.username} submitted report for '{task.title}'",
                    navigation_target=f"/task_details/{task.id}",
                )

        handle_side_effects(task, user, status_value)

        task.status = status_value
        task.save(
            update_fields=[
                "status",
                "start_time",
                "end_time",
                "actual_duration",
                "updated_at",
            ]
        )

        return task
    """
    @staticmethod
    def update_status(task, user, status_value):
        allowed_choices = ["TODO", "INPROGRESS", "REVIEW", "DONE"]
        if status_value not in allowed_choices:
                    raise InvalidStatusError()
        TASK_TRANSITIONS = {
            "TODO": ["INPROGRESS"],
            "INPROGRESS": ["TODO", "REVIEW"],
            "REVIEW": [],
            "DONE": [],
}
        allowed_transitions = TASK_TRANSITIONS.get(
            task.status,
            [],
)
        if status_value not in allowed_transitions:
            raise InvalidStatusError()


        is_project_manager = ProjectRole.objects.filter(
            project=task.project,
            user=user,
            role__in=['ADMIN', 'MANAGER'],
        ).exists()

        is_assignee = task.assigned_to_id == user.id
        if not is_assignee and not is_project_manager:
            raise PermissionDeniedError()
        if task.is_deleted or task.is_archived:
                raise InvalidStatusError()



        if task.status == "DONE" and status_value != "DONE":
            raise InvalidStatusError()
        if status_value == "INPROGRESS":
                blocking_dependencies = (
                    task.blocking_dependencies
                    .select_related("predecessor")
                )

                if blocking_dependencies.exists():
                    raise ValidationError({
                        "detail": (
                            "This task cannot be started because "
                            "it has incomplete dependencies."
                        ),
                        "code": "TASK_BLOCKED",
                        "blocked_by": [
                            {
                                "dependency_id": dependency.id,
                                "task_id": dependency.predecessor_id,
                                "title": dependency.predecessor.title,
                                "status": dependency.predecessor.status,
                            }
                            for dependency in blocking_dependencies
                        ],
                    })

                if not task.start_time:
                    task.start_time = timezone.now()

        if status_value == "REVIEW":
            report = TechnicalReportForm.objects.filter(
                task=task,
                user=task.assigned_to,
                status='SUBMITTED',
            ).order_by('-created_at').first()

            if not report:
                raise TechnicalReportMissingError()

            managers = User.objects.filter(
                projectrole__project=task.project,
                projectrole__role__in=['ADMIN', 'MANAGER'],
            ).distinct()
            for manager in managers:
                create_notification(
                    recipient=manager,
                    notification_type='REPORT_SUBMITTED',
                    title="New Technical Report Submitted",
                    message=f"Employee {user.get_full_name() or user.username} submitted a technical report for '{task.title}'.",
                    navigation_target=f"/task_details/{task.id}",
                )


        if status_value == "TODO":
            task.start_time = None
            task.end_time = None
            task.actual_duration = None

        if status_value == "DONE":
            task.end_time = timezone.now()
            task.actual_duration = task.end_time - task.start_time if task.start_time else None

        task.status = status_value
        task.save(update_fields=["status", "start_time", "end_time", "actual_duration", "updated_at"])


        TaskService.refresh_project_status(
            task.project,
        )

        return task




















    @staticmethod
    def review_technical_report(task, report, manager_user, feedback_text=None, new_status=None, quality=None):
        if new_status not in ['APPROVED', 'REJECTED']:
            raise ValidationError({"status": "Status must be APPROVED or REJECTED."})

        is_project_manager = ProjectRole.objects.filter(
            project=task.project,
            user=manager_user,
            role__in=['ADMIN', 'MANAGER'],
        ).exists()
        if not is_project_manager:
            raise PermissionDeniedError()

        now = timezone.now()

        if feedback_text:
            manager_entry = {
                "manager_name": manager_user.get_full_name() or manager_user.username,
                "note": feedback_text,
                "date": now.strftime("%Y-%m-%d %H:%M"),
            }
            current_feedbacks = report.manager_feedbacks or []
            current_feedbacks.append(manager_entry)
            report.manager_feedbacks = current_feedbacks
            report.manager_feedback = feedback_text

        if quality:
            report.quality = quality

        report.status = new_status
        report.save()

        if new_status == 'APPROVED':
            task.status = "DONE"
            task.end_time = now
            task.actual_duration = task.end_time - task.start_time if task.start_time else None

            create_notification(
                recipient=task.assigned_to,
                notification_type='SYSTEM_ALERT',
                title="Report accepted",
                message=f"Your report for task '{task.title}' was accepted.",
                navigation_target=f"/report_details/{report.id}",
            )
        else:
            task.status = "INPROGRESS"
            create_notification(
                recipient=task.assigned_to,
                notification_type='REPORT_REJECTED',
                title="Report Needs Adjustment",
                message=f"Your report for task '{task.title}' needs adjustments.",
                navigation_target=f"/report_details/{report.id}",
            )

        TaskService.refresh_project_status(task.project,)

        task.save()
        ActivityLog.objects.create(
            user=manager_user,
            action="REPORT_REVIEWED",
            action_id=report.id,
            changes={
                "subject_name": manager_user.username,
                "target_title": f"Report for {task.title}",
                "note": feedback_text,
                "status": new_status,
                "is_by_admin": True,
            },
        )

        return {
            "id": report.id,
            "status": report.status,
            "description": report.description,
            "manager_feedback": report.manager_feedback,
            "manager_feedbacks": report.manager_feedbacks,
            "task_status": task.status,
        }




    @staticmethod
    def perform_update(serializer, instance, user, status_value=None):
        if status_value == 'INPROGRESS' and not instance.start_time:
            serializer.save(start_time=timezone.now())
        elif status_value == 'DONE':
            now = timezone.now()
            actual_duration = now - instance.start_time if instance.start_time else None
            serializer.save(end_time=now, actual_duration=actual_duration)
        else:
            serializer.save()


    @staticmethod
    @transaction.atomic
    def restore_task(task, user):
        is_project_manager = ProjectRole.objects.filter(
            project=task.project,
            user=user,
            role__in=["ADMIN", "MANAGER"],
        ).exists()

        is_workspace_owner = (
            task.project.workspace.creator_id == user.id
        )

        if not is_project_manager and not is_workspace_owner:
            raise PermissionDeniedError()

        task.is_deleted = False
        task.deleted_at = None
        task.deleted_by = None

        task.save(
            update_fields=[
                "is_deleted",
                "deleted_at",
                "deleted_by",
                "updated_at",
            ]
        )
        TaskService.refresh_project_status(
            task.project,)

        return task




    @staticmethod
    @transaction.atomic
    def remove_dependency(*, task, predecessor, user):
        is_project_manager = ProjectRole.objects.filter(
            project=task.project,
            user=user,
            role__in=["ADMIN", "MANAGER"],
        ).exists()

        is_workspace_owner = (
            task.project.workspace.creator_id == user.id
        )

        if not is_project_manager and not is_workspace_owner:
            raise PermissionDeniedError()

        dependency = TaskDependency.objects.filter(
            predecessor=predecessor,
            successor=task,
        ).first()

        if not dependency:
            raise ValidationError({
                "detail": "Dependency relation was not found.",
                "code": "DEPENDENCY_NOT_FOUND",
            })

        dependency.delete()

        create_activity_log(
            user=user,
            action="GENERAL_UPDATE",
            action_id=task.id,
            subject_name=user.username,
            target_title=task.title,
            reason=(
                f"Dependency on task "
                f"'{predecessor.title}' was removed."
            ),
            is_by_admin=True,
        )

        return task


    @staticmethod
    @transaction.atomic
    def add_dependency(
        *,
        task,
        predecessor,
        user,
        dependency_type="BLOCKS",
    ):
        is_project_manager = ProjectRole.objects.filter(
            project=task.project,
            user=user,
            role__in=["ADMIN", "MANAGER"],
        ).exists()

        is_workspace_owner = (
            task.project.workspace.creator_id == user.id
        )

        if not is_project_manager and not is_workspace_owner:
            raise PermissionDeniedError()

        if task.is_deleted or predecessor.is_deleted:
            raise ValidationError({
                "detail": "Deleted tasks cannot be used in dependencies.",
                "code": "DELETED_TASK_DEPENDENCY",
            })

        if task.id == predecessor.id:
            raise ValidationError({
                "detail": "A task cannot depend on itself.",
                "code": "SELF_DEPENDENCY",
            })

        if task.project_id != predecessor.project_id:
            raise ValidationError({
                "detail": (
                    "Dependency tasks must belong to the same project."
                ),
                "code": "CROSS_PROJECT_DEPENDENCY",
            })

        if TaskDependency.objects.filter(
            predecessor=predecessor,
            successor=task,
        ).exists():
            raise ValidationError({
                "detail": "This dependency already exists.",
                "code": "DEPENDENCY_ALREADY_EXISTS",
            })

        if TaskService.creates_circular_dependency(
            predecessor=predecessor,
            successor=task,
        ):
            raise ValidationError({
                "detail": (
                    "This dependency cannot be created because "
                    "it would cause a circular dependency."
                ),
                "code": "CIRCULAR_DEPENDENCY",
            })

        dependency = TaskDependency.objects.create(
            predecessor=predecessor,
            successor=task,
            dependency_type=dependency_type,
            created_by=user,
        )

        create_activity_log(
            user=user,
            action="GENERAL_UPDATE",
            action_id=task.id,
            subject_name=user.username,
            target_title=task.title,
            reason=(
                f"Dependency on task "
                f"'{predecessor.title}' was added."
            ),
            is_by_admin=True,
        )

        return dependency



    @staticmethod
    def refresh_project_status(project):
        tasks = Task.objects.filter(
            project=project,
            is_deleted=False,
        )

        if not tasks.exists():
            new_status = "pending"

        elif tasks.exclude(status="DONE").exists():
            new_status = "on_going"

        else:
            new_status = "completed"

        if project.status != new_status:
            project.status = new_status
            project.save(
                update_fields=[
                    "status",
                    "updated_at",
                ]
            )





    @staticmethod
    @transaction.atomic
    def archive_task(*, task, user):
        is_project_manager = ProjectRole.objects.filter(
            project=task.project,
            user=user,
            role__in=["ADMIN", "MANAGER"],
        ).exists()

        is_workspace_owner = (
            task.project.workspace.creator_id == user.id
        )

        if not (
            is_project_manager
            or is_workspace_owner
        ):
            raise PermissionDeniedError()

        if task.is_deleted:
            raise ValidationError({
                "detail": "Deleted tasks cannot be archived.",
                "code": "DELETED_TASK_CANNOT_BE_ARCHIVED",
            })

        if task.is_archived:
            return task

        task.is_archived = True

        task.save(
            update_fields=[
                "is_archived",
                "updated_at",
            ]
        )

        TaskService.refresh_project_status(
            task.project,
        )

        create_activity_log(
            user=user,
            action="TASK_ARCHIVED",
            action_id=task.id,
            subject_name=user.username,
            target_title=task.title,
            reason=f"Task '{task.title}' was archived.",
            is_by_admin=True,
        )

        return task




    @staticmethod
    @transaction.atomic
    def unarchive_task(*, task, user):
        is_project_manager = ProjectRole.objects.filter(
            project=task.project,
            user=user,
            role__in=["ADMIN", "MANAGER"],
        ).exists()

        is_workspace_owner = (
            task.project.workspace.creator_id == user.id
        )

        if not (
            is_project_manager
            or is_workspace_owner
        ):
            raise PermissionDeniedError()

        if task.is_deleted:
            raise ValidationError({
                "detail": "Deleted tasks cannot be restored from archive.",
                "code": "DELETED_TASK_CANNOT_BE_UNARCHIVED",
            })

        if not task.is_archived:
            return task

        task.is_archived = False

        task.save(
            update_fields=[
                "is_archived",
                "updated_at",
            ]
        )

        TaskService.refresh_project_status(
            task.project,
        )

        create_activity_log(
            user=user,
            action="TASK_UNARCHIVED",
            action_id=task.id,
            subject_name=user.username,
            target_title=task.title,
            reason=f"Task '{task.title}' was restored from archive.",
            is_by_admin=True,
        )

        return task