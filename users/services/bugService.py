from django.db import transaction
from rest_framework.exceptions import PermissionDenied, ValidationError

from users.constants import create_activity_log, create_notification
from users.models import (
    BugReportForm,
    BugTaskLink,
    ProjectRole,
    Task,
    TaskFile,
    TaskImage,
    User,
)
from users.services import UserAvailabilityService
from users.services.task_service import (
    TaskService,
    validate_employee_task_availability,
)


class BugReportService:

    @staticmethod
    def _is_manager(user, project):
        is_project_manager = ProjectRole.objects.filter(
            project=project,
            user=user,
            role__in=["ADMIN", "MANAGER"],
        ).exists()

        is_workspace_owner = (
            project.workspace.creator_id == user.id
        )

        return is_project_manager or is_workspace_owner

    @staticmethod
    def _ensure_manager(user, project):
        if not BugReportService._is_manager(user, project):
            raise PermissionDenied(
                "Only project managers or admins can perform this action."
            )

    @staticmethod
    @transaction.atomic
    def create_bug(serializer, user):
        project = serializer.validated_data["project"]

        is_project_member = ProjectRole.objects.filter(
            project=project,
            user=user,
        ).exists()

        is_workspace_owner = (
            project.workspace.creator_id == user.id
        )

        if not is_project_member and not is_workspace_owner:
            raise PermissionDenied(
                "You must be a project member to report a bug."
            )

        bug = serializer.save(
            user=user,
            status="OPEN",
        )

        managers = User.objects.filter(
            projectrole__project=project,
            projectrole__role__in=["ADMIN", "MANAGER"],
            is_active=True,
            is_deleted=False,
        ).exclude(
            id=user.id,
        ).distinct()

        workspace_owner = project.workspace.creator

        recipients = list(managers)

        if (
            workspace_owner.id != user.id
            and workspace_owner.is_active
            and not workspace_owner.is_deleted
            and workspace_owner not in recipients
        ):
            recipients.append(workspace_owner)

        for manager in recipients:
            create_notification(
                recipient=manager,
                notification_type="BUG_REPORTED",
                title="New bug reported",
                message=(
                    f"{user.get_full_name() or user.username} "
                    f"reported a bug: '{bug.title}'."
                ),
                navigation_target=f"/bug-reports/{bug.id}",
            )

        create_activity_log(
            user=user,
            action="BUG_REPORTED",
            action_id=bug.id,
            changes={
                "subject_name": user.username,
                "target_title": bug.title,
                "reason": (
                    f"Bug '{bug.title}' was reported "
                    f"in project '{project.name}'."
                ),
                "is_by_admin": False,
            },
        )

        return bug
    @staticmethod
    @transaction.atomic
    def update_bug(bug, serializer, user):
        if bug.user_id != user.id:
            raise PermissionDenied(
                "You can only update bug reports created by you."
            )

        if bug.status != "OPEN":
            raise ValidationError(
                "Only open bug reports can be edited."
            )

        if bug.task_id is not None:
            raise ValidationError(
                "This bug has already been converted into a task."
            )

        bug = serializer.save()

        create_activity_log(
            user=user,
            action="BUG_UPDATED",
            action_id=bug.id,
            changes={
                "subject_name": user.username,
                "target_title": bug.title,
                "reason": f"Bug report '{bug.title}' was updated.",
                "is_by_admin": False,
            },
        )

        return bug

    @staticmethod
    @transaction.atomic
    def delete_bug(bug, user):
        if bug.user_id != user.id:
            raise PermissionDenied(
                "You can only delete bug reports created by you."
            )

        if bug.status != "OPEN" or bug.task_id is not None:
            raise ValidationError(
                "Only open bugs that were not converted "
                "to tasks can be deleted."
            )

        bug_id = bug.id
        bug_title = bug.title

        bug.delete()

        create_activity_log(
            user=user,
            action="BUG_DELETED",
            action_id=bug_id,
            changes={
                "subject_name": user.username,
                "target_title": bug_title,
                "reason": f"Bug report '{bug_title}' was deleted.",
                "is_by_admin": False,
            },
        )

    @staticmethod
    def _priority_from_dangerous_level(level):
        return {
            "LOW": "L",
            "MEDIUM": "M",
            "HIGH": "H",
        }.get(level, "M")

    @staticmethod
    @transaction.atomic
    def convert_to_task(
        bug,
        manager,
        assigned_to,
        expected_duration,
        due_date,
        priority=None,
        title=None,
        description=None,
        link=None,
        dependency_tasks=None,
        image_files=None,
        document_files=None,
    ):
        BugReportService._ensure_manager(
            manager,
            bug.project,
        )

        if bug.status != "OPEN":
            raise ValidationError({
                "detail": (
                    "Only open bug reports can be converted "
                    "to tasks."
                ),
                "code": "BUG_NOT_OPEN",
            })

        if assigned_to:
            is_member = ProjectRole.objects.filter(
                project=bug.project,
                user=assigned_to,
            ).exists()

            if not is_member:
                raise ValidationError({
                    "assigned_to": (
                        "The selected user is not a member "
                        "of this project."
                    )
                })

            UserAvailabilityService.ensure_active(
                assigned_to,
                action="task assignment",
            )
            validate_employee_task_availability(
                employee=assigned_to,
                due_date=due_date,
                expected_duration=expected_duration,
                actual_duration=None,
            )

        final_title = title if title is not None else bug.title
        final_description = (
            description if description is not None else bug.description
        )
        final_link = link if link is not None else bug.url

        task = Task.objects.create(
            creator=manager,
            project=bug.project,
            type="BUG",
            title=final_title,
            description=final_description,
            priority=(
                priority
                or BugReportService._priority_from_dangerous_level(
                    bug.dangerous_level
                )
            ),
            status="TODO",
            expected_duration=expected_duration,
            due_date=due_date,
            assigned_to=assigned_to,
            link=final_link,
        )

        for image in image_files or []:
            TaskImage.objects.create(
                task=task,
                user=manager,
                image=image,
            )

        for document in document_files or []:
            TaskFile.objects.create(
                task=task,
                user=manager,
                file=document,
            )

        TaskService.create_dependencies(
            task=task,
            dependency_tasks=dependency_tasks or [],
            created_by=manager,
        )

        BugTaskLink.objects.create(
            bug=bug,
            task=task,
            created_by=manager,
        )

        bug.task = task
        bug.save(
            update_fields=[
                "task",
                "updated_at",
            ]
        )

        if assigned_to:
            create_notification(
                recipient=assigned_to,
                notification_type="TASK_ASSIGNED",
                title="Bug task assigned",
                message=(
                    f"You were assigned to fix the bug task "
                    f"'{task.title}'."
                ),
                navigation_target=f"/tasks/{task.id}",
            )

        if bug.user_id != manager.id:
            create_notification(
                recipient=bug.user,
                notification_type="BUG_CONVERTED_TO_TASK",
                title="Bug accepted",
                message=(
                    f"Your bug report '{bug.title}' "
                    f"was converted into task #{task.id}."
                ),
                navigation_target=f"/tasks/{task.id}",
            )

        create_activity_log(
            user=manager,
            action="BUG_CONVERTED_TO_TASK",
            action_id=bug.id,
            changes={
                "subject_name": (
                    manager.get_full_name()
                    or manager.username
                ),
                "target_title": bug.title,
                "reason": (
                    f"Bug report '{bug.title}' was converted "
                    f"to task #{task.id}."
                ),
                "is_by_admin": True,
            },
        )

        return task
    @staticmethod
    @transaction.atomic
    def verify_fix(
        bug,
        user,
    ):
        if bug.user_id != user.id:
            raise PermissionDenied(
                "Only the bug reporter can verify the fix."
            )

        linked_tasks = BugTaskLink.objects.filter(
            bug=bug,
            task__is_deleted=False,
            task__is_archived=False,
        ).select_related(
            "task",
        )

        if not linked_tasks.exists():
            raise ValidationError({
                "detail": (
                    "This bug report is not linked "
                    "to any active task."
                ),
                "code": "BUG_HAS_NO_LINKED_TASKS",
            })

        unfinished_tasks = linked_tasks.exclude(
            task__status="DONE",
        )

        if unfinished_tasks.exists():
            raise ValidationError({
                "detail": (
                    "All linked tasks must be completed "
                    "before verifying the fix."
                ),
                "code": "BUG_HAS_UNFINISHED_TASKS",
                "tasks": [
                    {
                        "id": link.task_id,
                        "title": link.task.title,
                        "status": link.task.status,
                    }
                    for link in unfinished_tasks
                ],
            })

        if bug.status not in ["OPEN", "FIXED"]:
            raise ValidationError({
                "detail": (
                    "This bug cannot be verified "
                    "in its current state."
                ),
                "code": "BUG_CANNOT_BE_VERIFIED",
                "bug_status": bug.status,
            })

        bug.status = "VERIFIED"
        bug.save(
            update_fields=[
                "status",
                "updated_at",
            ]
        )

        create_activity_log(
            user=user,
            action="BUG_VERIFIED",
            action_id=bug.id,
            changes={
                "subject_name": (
                    user.get_full_name()
                    or user.username
                ),
                "target_title": bug.title,
                "reason": (
                    f"The fix for bug '{bug.title}' "
                    "was verified by the reporter."
                ),
                "is_by_admin": False,
            },
        )

        return bug

    @staticmethod
    @transaction.atomic
    def close_bug(bug, manager, result=None):
        BugReportService._ensure_manager(
            manager,
            bug.project,
        )

        if bug.status == "CLOSED":
            raise ValidationError({
            "status": "This bug report is already closed."
        })
        if not result:
            raise ValidationError({
            "result": "Closing reason is required."
        })
        if (
            bug.task_id
            and bug.task.status != "DONE"
        ):
            raise ValidationError({
                "task": (
                    "This bug is linked to an active task. "
                    "Choose whether to keep or archive the task "
                    "before closing the bug."
                ),
                "code": "BUG_HAS_ACTIVE_TASK",
                "task_id": bug.task_id,
                "task_status": bug.task.status,
            })
        active_tasks = BugTaskLink.objects.filter(
                bug=bug,
                task__status__in=[
                    "TODO",
                    "INPROGRESS",
                    "REVIEW",
                    "PAUSED",
                ],
                task__is_deleted=False,
                task__is_archived=False,
            ).select_related(
                "task",
            )

        if active_tasks.exists():
            raise ValidationError({
                "detail": (
                    "The bug cannot be closed while it has "
                    "active linked tasks."
                ),
                "code": "BUG_HAS_ACTIVE_TASKS",
                "tasks": [
                    {
                        "id": link.task_id,
                        "title": link.task.title,
                        "status": link.task.status,
                    }
                    for link in active_tasks
                ],
            })
        has_linked_tasks = BugTaskLink.objects.filter(
            bug=bug,
        ).exists()

        if has_linked_tasks and bug.status != "VERIFIED":
            raise ValidationError({
                "detail": (
                    "The bug reporter must verify the fix "
                    "before closing the bug."
                ),
                "code": "BUG_FIX_NOT_VERIFIED",
            })

        bug.status = "CLOSED"

        if result is not None:
            bug.result = result

        bug.save(
            update_fields=[
                "status",
                "result",
                "updated_at",
            ]
        )

        create_notification(
            recipient=bug.user,
            notification_type="BUG_CLOSED",
            title="Bug closed",
            message=f"Your bug report '{bug.title}' was closed.",
            navigation_target=f"/bug-reports/{bug.id}",
        )

        return bug