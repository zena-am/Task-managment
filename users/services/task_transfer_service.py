from datetime import timedelta

from django.db import transaction
from django.utils import timezone
from rest_framework.exceptions import ValidationError

from users.constants import create_activity_log, create_notification
from users.errors.exceptions import PermissionDeniedError
from users.models import LeaveTaskAction, Notification, Project, ProjectRole, Task, User
from users.services import UserAvailabilityService
from users.services.task_service import validate_employee_task_availability


class TaskTransferService:



    @staticmethod
    def get_orphaned_tasks(project, params=None):
        params = params or {}

        queryset = Task.objects.filter(
            project=project,
            assignment_state__in=[
                "UNASSIGNED_NEW",
                "UNASSIGNED_RETURNED",
            ]

        )

        state = params.get("assignment_state")
        if state:
            queryset = queryset.filter(assignment_state=state)

        return queryset.order_by("-id")

    @staticmethod
    @transaction.atomic
    def assign_unassigned_tasks(
        project,
        new_assignee,
        performed_by,
    ):
        if not TaskTransferService._can_manage_project(
            project,
            performed_by,
        ):
            raise PermissionDeniedError()

        UserAvailabilityService.ensure_active(
            new_assignee,
            action="task assignment",
        )

        is_project_member = ProjectRole.objects.filter(
            project=project,
            user=new_assignee,
        ).exists()

        if not is_project_member:
            raise ValidationError({
                "new_assignee": (
                    "The selected user is not a member "
                    "of this project."
                )
            })

        tasks = Task.objects.select_for_update().filter(
            project=project,
            assigned_to__isnull=True,
            assignment_state__in=[
                "UNASSIGNED_NEW",
                "UNASSIGNED_RETURNED",
            ],
            is_deleted=False,
            is_archived=False,
        )

        count = 0

        for task in tasks:
            validate_employee_task_availability(
                employee=new_assignee,
                project=project,
                due_date=task.due_date,
                expected_duration=task.expected_duration,
                actual_duration=task.actual_duration,
            )

            task.assigned_to = new_assignee
            task.assignment_state = "ASSIGNED"
            task.status = "TODO"
            task.start_time = None
            task.end_time = None

            task.save(
                update_fields=[
                    "assigned_to",
                    "assigned_at",
                    "assignment_state",
                    "status",
                    "start_time",
                    "end_time",
                    "updated_at",
                ]
            )

            create_activity_log(
                user=performed_by,
                action="GENERAL_UPDATE",
                action_id=task.id,
                subject_name=performed_by.username,
                target_title=task.title,
                reason=(
                    f"Task assigned to "
                    f"{new_assignee.username}."
                ),
                is_by_admin=True,
            )

            create_notification(
                recipient=new_assignee,
                notification_type="SYSTEM_ALERT",
                title="New Task Assigned",
                message=(
                    f"You have been assigned to task "
                    f"'{task.title}' in project "
                    f"'{project.name}'."
                ),
                navigation_target=(
                    f"/task_details/{task.id}"
                ),
            )

            count += 1

        return count

    @staticmethod
    @transaction.atomic
    def assign_task_to_user(
        *,
        task,
        new_assignee,
        performed_by,
        project,
    ):
        if task.project_id != project.id:
            raise ValidationError({
                "project": (
                    "The task does not belong "
                    "to this project."
                )
            })

        if not TaskTransferService._can_manage_project(
            user=performed_by,
            project=project,
        ):
            raise PermissionDeniedError()

        if task.is_deleted or task.is_archived:
            raise ValidationError({
                "task": (
                    "Deleted or archived tasks "
                    "cannot be reassigned."
                )
            })

        if task.status == "DONE":
            raise ValidationError({
                "task": (
                    "Completed tasks cannot be reassigned."
                )
            })

        UserAvailabilityService.ensure_active(
            new_assignee,
            action="task assignment",
        )

        is_project_member = ProjectRole.objects.filter(
            project=project,
            user=new_assignee,
        ).exists()

        if not is_project_member:
            raise ValidationError({
                "new_assignee": (
                    "The selected user is not "
                    "a member of this project."
                )
            })

        if task.assigned_to_id == new_assignee.id:
            raise ValidationError({
                "new_assignee": (
                    "This task is already assigned "
                    "to the selected user."
                )
            })

        validate_employee_task_availability(
            employee=new_assignee,
            project=project,
            due_date=task.due_date,
            expected_duration=task.expected_duration,
            actual_duration=timedelta(0),
        )



        leave_pause_action = (
            LeaveTaskAction.objects
            .select_for_update()
            .filter(
                task=task,
                action="PAUSE_TASK",
                is_resolved=True,
                request__status__in=[
                    "ACTION_REQUIRED",
                    "PENDING",
                    "ON_HOLD",
                    "APPROVED",
                ],
            )
            .order_by("-resolved_at")
            .first()
        )

        previous_assignee = task.assigned_to


        task.assigned_to = new_assignee
        task.assignment_state = "ASSIGNED"

        task.status = "TODO"

        task.start_time = None
        task.end_time = None

        task.actual_duration = timedelta(0)

        task.save(
            update_fields=[
                "assigned_to",
                "assigned_at",
                "assignment_state",
                "status",
                "start_time",
                "end_time",
                "actual_duration",
                "updated_at",
            ]
        )


        if leave_pause_action is not None:
            leave_pause_action.action = "TRANSFER_TASK"

            leave_pause_action.new_assignee = (
                new_assignee
            )

            leave_pause_action.resolved_by = (
                performed_by
            )

            leave_pause_action.resolved_at = (
                timezone.now()
            )

            leave_pause_action.save(
                update_fields=[
                    "action",
                    "new_assignee",
                    "resolved_by",
                    "resolved_at",
                    "updated_at",
                ]
            )

        create_activity_log(
            user=performed_by,
            action="GENERAL_UPDATE",
            action_id=task.id,
            subject_name=performed_by.username,
            target_title=task.title,
            reason=(
                f"Task reassigned from "
                f"{previous_assignee.username if previous_assignee else 'unassigned'} "
                f"to {new_assignee.username}."
            ),
            is_by_admin=True,
        )

        create_notification(
            recipient=new_assignee,
            notification_type="SYSTEM_ALERT",
            title="Task Assigned",
            message=(
                f"You have been assigned to task "
                f"'{task.title}' in project "
                f"'{project.name}'."
            ),
            navigation_target=(
                f"/task_details/{task.id}"
            ),
        )

        if (
            previous_assignee
            and previous_assignee.id
            != new_assignee.id
        ):
            create_notification(
                recipient=previous_assignee,
                notification_type="TASK_UNASSIGNED",
                title="Task Reassigned",
                message=(
                    f"Task '{task.title}' was "
                    f"reassigned to another member."
                ),
                navigation_target=(
                    f"/task_details/{task.id}"
                ),
            )

        return task
    @staticmethod
    def _can_manage_project(
        *,
        user,
        project,
    ):
        is_workspace_owner = (
            project.workspace.creator_id == user.id
        )

        is_project_manager = ProjectRole.objects.filter(
            project=project,
            user=user,
            role__in=["ADMIN", "MANAGER"],
        ).exists()

        return (
            is_workspace_owner
            or is_project_manager
        )

class ProjectService:

    @staticmethod
    def get_projects_without_manager():

        managed_projects_ids = ProjectRole.objects.filter(role__in=["MANAGER", "ADMIN"]).values_list("project_id", flat=True)

        unmanaged_projects = Project.objects.exclude(id__in=managed_projects_ids)

        return unmanaged_projects


    @staticmethod
    def assign_new_manager(project, new_manager, performed_by):

        project_role = ProjectRole.objects.filter(
            project=project,
            user=new_manager
        ).first()

        if not project_role:
            raise ValidationError(
                "User is not a member of this project."
            )

        project_role.role = "MANAGER"
        project_role.save(update_fields=["role"])

        create_activity_log(
            user=performed_by,
            action="ROLE_UPDATED",
            action_id=project.id,
            changes={
                "subject_name": new_manager.username,
                "target_title": project.name,
                "reason": f"{new_manager.username} was assigned as manager of project {project.name}.",
                "is_by_admin": True
            }
        )

        Notification.objects.create(
            recipient=new_manager,
            notification_type="SYSTEM_ALERT",
            title="Project Manager Assigned",
            message=f"You have been assigned as manager of project '{project.name}'.",
            navigation_target=f"/projects/{project.id}"
        )


        return project_role




class RoleService:
    @staticmethod
    @transaction.atomic
    def set_user_role(
        project,
        user,
        new_role,
        performed_by,
    ):
        allowed_roles = [
            "ADMIN",
            "MANAGER",
            "EMPLOYEE",
        ]

        if new_role not in allowed_roles:
            raise ValidationError({
                "role": "Invalid project role."
            })

        project_role = ProjectRole.objects.filter(
            project=project,
            user=user,
        ).first()

        if not project_role:
            raise ValidationError({
                "user": (
                    "User is not a member "
                    "of this project."
                )
            })
        can_update_role = (
            project.workspace.creator_id == performed_by.id
            or ProjectRole.objects.filter(
                project=project,
                user=performed_by,
                role__in=["ADMIN", "MANAGER"],
            ).exists()
        )

        if not can_update_role:
            raise PermissionDeniedError()
        performed_by_role = ProjectRole.objects.filter(
            project=project,
            user=performed_by,
        ).values_list(
            "role",
            flat=True,
        ).first()

        is_workspace_owner = (
            project.workspace.creator_id
            == performed_by.id
        )

        is_project_admin = (
            performed_by_role == "ADMIN"
        )

        is_project_manager = (
            performed_by_role == "MANAGER"
        )

        if not (
            is_workspace_owner
            or is_project_admin
            or is_project_manager
        ):
            raise PermissionDeniedError()

        if (
            is_project_manager
            and not is_workspace_owner
        ):
            if old_role == "ADMIN":
                raise ValidationError({
                    "role": (
                        "Project managers cannot change "
                        "the ADMIN role."
                    )
                })

            if new_role == "ADMIN":
                raise ValidationError({
                    "role": (
                        "Project managers cannot promote "
                        "members to ADMIN."
                    )
                })
        old_role = project_role.role

        if old_role == new_role:
            return project_role

        project_role.role = new_role

        project_role.save(
            update_fields=[
                "role",
            ]
        )

        create_activity_log(
            user=performed_by,
            action="ROLE_UPDATED",
            action_id=project.id,
            subject_name=user.username,
            target_title=project.name,
            reason=(
                f"Role changed from {old_role} "
                f"to {new_role}."
            ),
            is_by_admin=True,
        )

        create_notification(
            recipient=user,
            notification_type="SYSTEM_ALERT",
            title="Project Role Updated",
            message=(
                f"Your role in project "
                f"'{project.name}' was changed "
                f"from {old_role} to {new_role}."
            ),
            navigation_target=(
                f"/projects/{project.id}"
            ),
        )

        return project_role

    @staticmethod
    def transfer_tasks(
        project,
        new_assignee,
        performed_by,
    ):
        return TaskTransferService.assign_unassigned_tasks(
            project=project,
            new_assignee=new_assignee,
            performed_by=performed_by,
        )



