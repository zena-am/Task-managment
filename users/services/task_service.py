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
from users.models import ActivityLog, LeaveTaskAction, Notification, ProjectRole, RequestForm, Task, TaskDependency, TaskFile, TaskImage, TechnicalReportForm, User
from users.services import UserAvailabilityService
from users.services.invitationsService import InvitationService
from users.services import UserAvailabilityService
from users.services.invitationsService import InvitationService
from users.services.working_time_service import WorkingTimeService
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
        project,
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
            project=project,
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
def get_active_leave_pause_action(task):
    return (
        LeaveTaskAction.objects
        .filter(
            task=task,
            action="PAUSE_TASK",
            is_resolved=True,
            request__status__in=[
                "ACTION_REQUIRED",
                "PENDING",
                "APPROVED",
                "ON_HOLD",
            ],
        )
        .select_related(
            "request",
            "request__user",
        )
        .order_by("-resolved_at")
        .first()
    )

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

        can_claim = ProjectRole.objects.filter(
            project=task.project,
            user=user,
            role__in=["ADMIN", "MANAGER"],
        ).exists()
        if not can_claim:
            raise PermissionDeniedError()

        task.assigned_to = user
        task.status = "TODO"
        task.save(update_fields=["assigned_to","assigned_at", "status", "updated_at"])

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

    @transaction.atomic
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
            image_files = validated_data.pop("image_files",[],)
            document_files = validated_data.pop("document_files", [],)
            validated_data.pop(
                "remove_image_ids",
                [],
            )

            validated_data.pop(
                "remove_file_ids",
                [],
            )
            assigned_user = validated_data.get("assigned_to")
            project = validated_data.get("project")
            due_date = validated_data.get("due_date")
            expected_duration = validated_data.get("expected_duration")
            actual_duration = validated_data.get("actual_duration")



            workspace = project.workspace
            if not due_date and expected_duration:

                due_date = WorkingTimeService.add_working_hours(
                    workspace=workspace,
                    start_datetime=timezone.now(),
                    hours=(
                        expected_duration.total_seconds()
                        / 3600
                    ),
                )

                validated_data["due_date"] = due_date
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
                project=project,
                due_date=due_date,
                expected_duration=expected_duration,
                actual_duration=actual_duration,
            )
                # ---------------------------------------------------------
            if due_date:
                now = timezone.now()

                if due_date < now:
                    raise ValidationError({
                        "due_date": "Due date cannot be in the past."
                    })

                if expected_duration:
                    available_hours = (
                        WorkingTimeService.get_working_hours_between(
                            workspace=workspace,
                            start_datetime=now,
                            end_datetime=due_date,
                        )
                    )

                    expected_hours = (
                        expected_duration.total_seconds()
                        / 3600
                    )
                    if expected_hours > available_hours:
                        raise ValidationError({
            "due_date": (
                "The selected due date does not provide "
                "enough working hours for this task."
            ),
            "code": (
                "INSUFFICIENT_WORKING_TIME"
            ),
            "required_hours": expected_hours,
            "available_hours": available_hours,
        })
            now = timezone.now()

            validated_data.pop(
                "assigned_at",
                None
            )

            task = Task.objects.create(
                creator=user,
                status="TODO",
                assignment_state=(
                    "ASSIGNED"
                    if assigned_user is not None
                    else "UNASSIGNED_NEW"
                ),
                assigned_at=(now
                if assigned_user is not None
                else None),
                **validated_data,)

            for image in image_files:
                TaskImage.objects.create(
                    task=task,
                    user=user,
                    image=image,
                )

            for file in document_files:
                TaskFile.objects.create(
                    task=task,
                    user=user,
                    file=file,
                )
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




        if task.status != "TODO":
            raise ValidationError({
                "detail": (
                    "Dependencies can only be created "
                    "before the task has started."
                ),
                "code": "DEPENDENCY_ADD_NOT_ALLOWED",
                "task_id": task.id,
                "task_status": task.status,
            })
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
            if (
                    predecessor.due_date
                    and task.due_date
                ):

                    available_hours = (
                        WorkingTimeService.get_working_hours_between(
                            workspace=task.project.workspace,
                            start_datetime=predecessor.due_date,
                            end_datetime=task.due_date,
                        )
                    )

                    if available_hours <= 0:
                        raise ValidationError({
                            "detail": (
                                "The dependent task has no available "
                                "working time after the predecessor task."
                            ),
                            "code": "NO_WORKING_TIME_BETWEEN_DEPENDENCIES",
                            "predecessor": {
                                "id": predecessor.id,
                                "title": predecessor.title,
                                "due_date": predecessor.due_date,
                            },
                            "successor": {
                                "id": task.id,
                                "title": task.title,
                                "due_date": task.due_date,
                            },
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

    @staticmethod
    def update_status(task, user, status_value):
        allowed_choices = [
            "TODO",
            "INPROGRESS",
            "PAUSED",
            "REVIEW",
            "DONE",
        ]

        if status_value not in allowed_choices:
            raise InvalidStatusError()

        transitions = {
            "TODO": [
                "INPROGRESS",
                "DONE",
            ],
            "INPROGRESS": [
                "TODO",
                "PAUSED",
                "REVIEW",
                "DONE",
            ],
            "PAUSED": [
                "INPROGRESS",
            ],
            "REVIEW": [],
            "DONE": [],
        }

        current_status = task.status

        allowed_transitions = transitions.get(
            current_status,
            [],
        )

        if status_value not in allowed_transitions:
            raise InvalidStatusError()

        is_project_manager = ProjectRole.objects.filter(
            project=task.project,
            user=user,
            role__in=["ADMIN", "MANAGER"],
        ).exists()

        is_assignee = task.assigned_to_id == user.id

        if not is_assignee:
            raise PermissionDeniedError()

        if task.is_deleted or task.is_archived:
            raise InvalidStatusError()

        if current_status == "DONE":
            raise InvalidStatusError()

        if status_value == "DONE":
            if not (
                is_project_manager
                and is_assignee
            ):
                raise InvalidStatusError()

            if task.is_blocked:
                raise ValidationError({
                    "detail": (
                        "This task cannot be completed because "
                        "it has incomplete dependencies."
                    ),
                    "code": "TASK_BLOCKED",
                })

        now = timezone.now()

        # ==========================================
        # Resume from PAUSED
        # ==========================================

        if (
            current_status == "PAUSED"
            and status_value == "INPROGRESS"
        ):
            leave_pause_action = (
                get_active_leave_pause_action(task)
            )

            if leave_pause_action is not None:
                raise ValidationError({
                    "detail": (
                        "This task is paused because of a leave "
                        "request and cannot be resumed manually."
                    ),
                    "code": "TASK_PAUSED_FOR_LEAVE",
                    "leave_action_id": (
                        leave_pause_action.id
                    ),
                    "leave_request_id": (
                        leave_pause_action.request_id
                    ),
                })

        # ==========================================
        # Start / Resume
        # ==========================================

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
                        for dependency
                        in blocking_dependencies
                    ],
                })

            task.start_time = now
            task.end_time = None


        if status_value == "PAUSED":
            if task.start_time:
                worked_duration = (
                    now - task.start_time
                )

                task.actual_duration = (
                    task.actual_duration
                    or timedelta(0)
                ) + worked_duration

            task.start_time = None
            task.end_time = None

        # ==========================================
        # Send to Review
        # ==========================================

        if status_value == "REVIEW":
            report = TechnicalReportForm.objects.filter(
                task=task,
                user=task.assigned_to,
                status="SUBMITTED",
            ).order_by(
                "-created_at"
            ).first()

            if not report:
                raise TechnicalReportMissingError()

            if task.start_time:
                worked_duration = (
                    now - task.start_time
                )

                task.actual_duration = (
                    task.actual_duration
                    or timedelta(0)
                ) + worked_duration

                task.start_time = None

            task.end_time = None

            managers = User.objects.filter(
                projectrole__project=task.project,
                projectrole__role__in=[
                    "ADMIN",
                    "MANAGER",
                ],
            ).distinct()

            for manager in managers:
                create_notification(
                    recipient=manager,
                    notification_type="REPORT_SUBMITTED",
                    title="New Technical Report Submitted",
                    message=(
                        f"Employee "
                        f"{user.get_full_name() or user.username} "
                        f"submitted a technical report for "
                        f"'{task.title}'."
                    ),
                    navigation_target=(
                        f"/task_details/{task.id}"
                    ),
                )

        # ==========================================
        # Reset to TODO
        # ==========================================

        if status_value == "TODO":
            task.start_time = None
            task.end_time = None
            task.actual_duration = timedelta(0)

        # ==========================================
        # Done
        # ==========================================

        if status_value == "DONE":
            if task.start_time:
                worked_duration = (
                    now - task.start_time
                )

                task.actual_duration = (
                    task.actual_duration
                    or timedelta(0)
                ) + worked_duration

            task.start_time = None
            task.end_time = now

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

        TaskService.refresh_project_status(
            task.project,
        )

        return task



    @staticmethod
    def validate_dependency_due_date(
        *,
        task,
        new_due_date,
    ):
        if not new_due_date:
            return

        invalid_predecessor = (
            TaskDependency.objects
            .filter(
                successor=task,
                dependency_type="BLOCKS",
                predecessor__due_date__gt=new_due_date,
            )
            .select_related("predecessor")
            .order_by("predecessor__due_date")
            .first()
        )

        if invalid_predecessor:
            predecessor = (
                invalid_predecessor.predecessor
            )

            raise ValidationError({
                "detail": (
                    "The task due date cannot be earlier "
                    "than one of its predecessor tasks."
                ),
                "code": "INVALID_DEPENDENCY_DATES",
                "predecessor": {
                    "id": predecessor.id,
                    "title": predecessor.title,
                    "due_date": (
                        predecessor.due_date.isoformat()
                        if predecessor.due_date
                        else None
                    ),
                },
                "task": {
                    "id": task.id,
                    "title": task.title,
                    "new_due_date": (
                        new_due_date.isoformat()
                    ),
                },
            })

        invalid_successor = (
            TaskDependency.objects
            .filter(
                predecessor=task,
                dependency_type="BLOCKS",
                successor__due_date__lt=new_due_date,
            )
            .select_related("successor")
            .order_by("successor__due_date")
            .first()
        )

        if invalid_successor:
            successor = (
                invalid_successor.successor
            )

            raise ValidationError({
                "detail": (
                    "The task due date cannot be later "
                    "than one of the tasks that depend on it."
                ),
                "code": "INVALID_DEPENDENCY_DATES",
                "successor": {
                    "id": successor.id,
                    "title": successor.title,
                    "due_date": (
                        successor.due_date.isoformat()
                        if successor.due_date
                        else None
                    ),
                },
                "task": {
                    "id": task.id,
                    "title": task.title,
                    "new_due_date": (
                        new_due_date.isoformat()
                    ),
                },
            })
    """
        @staticmethod
    def update_status(task, user, status_value):
        allowed_choices = ["TODO", "INPROGRESS", "REVIEW", "DONE"]
        if status_value not in allowed_choices:
                    raise InvalidStatusError()
        TASK_TRANSITIONS = {
            "TODO": ["INPROGRESS", "DONE"],
            "INPROGRESS": ["TODO", "REVIEW", "DONE"],
            "PAUSED": ["INPROGRESS", "DONE"],
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
        if not is_assignee:
            raise PermissionDeniedError()

        if status_value == "DONE":
            if not (is_project_manager and is_assignee):
                raise InvalidStatusError()

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









    """












    @staticmethod
    def review_technical_report(
        task,
        report,
        manager_user,
        feedback_text=None,
        new_status=None,
        quality=None,
    ):
        if new_status not in [
            "APPROVED",
            "REJECTED",
        ]:
            raise ValidationError({
                "status": (
                    "Status must be APPROVED or REJECTED."
                )
            })

        is_project_manager = ProjectRole.objects.filter(
            project=task.project,
            user=manager_user,
            role__in=[
                "ADMIN",
                "MANAGER",
            ],
        ).exists()

        if not is_project_manager:
            raise PermissionDeniedError()

        if report.status != "SUBMITTED":
            raise ValidationError({
                "status": (
                    "Only submitted reports can be reviewed."
                )
            })

        if (
            new_status == "APPROVED"
            and not quality
        ):
            raise ValidationError({
                "quality": (
                    "Quality evaluation is required."
                )
            })

        now = timezone.now()

        if feedback_text:
            manager_entry = {
                "manager_name": (
                    manager_user.get_full_name()
                    or manager_user.username
                ),
                "note": feedback_text,
                "date": now.strftime(
                    "%Y-%m-%d %H:%M"
                ),
            }

            current_feedbacks = (
                report.manager_feedbacks
                or []
            )

            current_feedbacks.append(
                manager_entry
            )

            report.manager_feedbacks = (
                current_feedbacks
            )

            report.manager_feedback = (
                feedback_text
            )

        if quality:
            report.quality = quality

        report.status = new_status
        report.save()


        if new_status == "APPROVED":

            if task.start_time:
                worked_duration = (
                    now - task.start_time
                )

                task.actual_duration = (
                    task.actual_duration
                    or timedelta(0)
                ) + worked_duration

            task.status = "DONE"
            task.start_time = None
            task.end_time = now

            create_notification(
                recipient=task.assigned_to,
                notification_type="SYSTEM_ALERT",
                title="Report accepted",
                message=(
                    f"Your report for task "
                    f"'{task.title}' was accepted."
                ),
                navigation_target=(
                    f"/report_details/{report.id}"
                ),
            )


        else:

            task.status = "INPROGRESS"
            task.start_time = now
            task.end_time = None

            create_notification(
                recipient=task.assigned_to,
                notification_type="REPORT_REJECTED",
                title="Report Needs Adjustment",
                message=(
                    f"Your report for task "
                    f"'{task.title}' needs adjustments."
                ),
                navigation_target=(
                    f"/report_details/{report.id}"
                ),
            )

            create_activity_log(
                user=manager_user,
                action="REPORT_REJECTED",
                action_id=report.id,
                changes={
                    "subject_name": (
                        manager_user.username
                    ),
                    "target_title": task.title,
                    "reason": feedback_text,
                    "is_by_admin": True,
                },
            )

        task.save(
            update_fields=[
                "status",
                "start_time",
                "end_time",
                "actual_duration",
                "updated_at",
            ]
        )

        TaskService.refresh_project_status(
            task.project,
        )

        ActivityLog.objects.create(
            user=manager_user,
            action="REPORT_REVIEWED",
            action_id=report.id,
            changes={
                "subject_name": (
                    manager_user.username
                ),
                "target_title": (
                    f"Report for {task.title}"
                ),
                "note": feedback_text,
                "status": new_status,
                "is_by_admin": True,
            },
        )

        return {
            "id": report.id,
            "status": report.status,
            "description": report.description,
            "manager_feedback": (
                report.manager_feedback
            ),
            "manager_feedbacks": (
                report.manager_feedbacks
            ),
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


        if task.status != "TODO":
            raise ValidationError({
                "detail": (
                    "Dependencies can only be added "
                    "before the task has started."
                ),
                "code": "DEPENDENCY_ADD_NOT_ALLOWED",
                "task_id": task.id,
                "task_status": task.status,
            })
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

        if dependency_type not in dict(
            TaskDependency.DEPENDENCY_TYPES
        ):
            raise ValidationError({
                "dependency_type": (
                    "Invalid dependency type."
                ),
                "code": "INVALID_DEPENDENCY_TYPE",
            })

        if (
            dependency_type == "BLOCKS"
            and predecessor.due_date
            and task.due_date
        ):
            available_hours = (
                WorkingTimeService.get_working_hours_between(
                    workspace=task.project.workspace,
                    start_datetime=predecessor.due_date,
                    end_datetime=task.due_date,
                )
            )
            if available_hours <= 0:
                raise ValidationError({
            "detail": (
                "The dependent task has no available "
                "working time after the predecessor task."
            ),
            "code": "NO_WORKING_TIME_BETWEEN_DEPENDENCIES",
            "predecessor": {
                "id": predecessor.id,
                "title": predecessor.title,
                "due_date": predecessor.due_date,
            },
            "successor": {
                "id": task.id,
                "title": task.title,
                "due_date": task.due_date,
            },
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



        active_dependents = (
            TaskDependency.objects
            .filter(
                predecessor=task,
                dependency_type="BLOCKS",
                successor__is_deleted=False,
                successor__is_archived=False,
            )
            .exclude(
                successor__status="DONE",
            )
            .select_related("successor")
        )

        if (
            task.status != "DONE"
            and active_dependents.exists()
        ):
            dependent = active_dependents.first()

            raise ValidationError({
                "detail": (
                    "This task cannot be archived because "
                    "other active tasks still depend on it."
                ),
                "code": "TASK_HAS_ACTIVE_DEPENDENTS",
                "dependent_task": {
                    "id": dependent.successor.id,
                    "title": dependent.successor.title,
                    "status": dependent.successor.status,
                },
            })
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