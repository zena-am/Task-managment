from django.db.models import Q
from users.errors.exceptions import PermissionDeniedError
from users.models import ActivityLog, ProjectRole


class TaskHistoryService:

    TASK_ACTIONS = [
        "TASK_CREATED",
        "TASK_UPDATED",
        "TASK_STATUS_CHANGED",
        "TASK_ASSIGNED",
        "TASK_REASSIGNED",
        "TASK_CLAIMED",
        "TASK_DELETED",
        "TASK_RESTORED",
        "TASK_ARCHIVED",
        "TASK_UNARCHIVED",
        "TASK_DUPLICATED",
        "DEPENDENCY_ADDED",
        "DEPENDENCY_REMOVED",
        "REPORT_SUBMITTED",
        "REPORT_REVIEWED",
    ]

    @staticmethod
    def get_task_history(
        *,
        task,
        user,
    ):
        is_project_member = ProjectRole.objects.filter(
            project=task.project,
            user=user,
        ).exists()

        is_workspace_owner = (
            task.project.workspace.creator_id
            == user.id
        )

        if not (
            is_project_member
            or is_workspace_owner
        ):
            raise PermissionDeniedError()

        return (
            ActivityLog.objects.filter(
                action__in=(
                    TaskHistoryService
                    .TASK_ACTIONS
                ),
            )
            .filter(
                Q(
                    changes__task_id=task.id,
                )
                | Q(
                    action_id=task.id,
                    action__in=[
                        "TASK_CREATED",
                        "TASK_UPDATED",
                        "TASK_STATUS_CHANGED",
                        "TASK_ASSIGNED",
                        "TASK_REASSIGNED",
                        "TASK_CLAIMED",
                        "TASK_DELETED",
                        "TASK_RESTORED",
                        "TASK_ARCHIVED",
                        "TASK_UNARCHIVED",
                        "TASK_DUPLICATED",
                        "DEPENDENCY_ADDED",
                        "DEPENDENCY_REMOVED",
                    ],
                )
            )
            .select_related("user")
            .order_by("-created_at")
        )