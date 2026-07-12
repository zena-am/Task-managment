from django.db import transaction
from django.db.models import Q

from users.constants import create_activity_log
from users.errors.exceptions import (
    AccountAlreadyDeletedError,
    AccountIsLastProjectManagerError,
    AccountOwnsWorkspacesError,
)
from users.models import (
    BugReportForm,
    Invitation,
    ProjectRole,
    Task,
    User,
    WorkSpaceMember,
)


class UserService:
    @staticmethod
    @transaction.atomic
    def soft_delete_account(user):
        """
        Soft-delete an account while preserving historical records.

        - Blocks workspace owners until ownership is transferred.
        - Blocks the last active project manager/admin until a replacement exists.
        - Unassigns unfinished tasks and non-closed bug reports.
        - Keeps DONE tasks and historical reports/logs linked to the deleted user.
        - Removes active workspace/project memberships.
        - Rejects pending invitations addressed to the account.
        """
        locked_user = User.all_objects.select_for_update().get(pk=user.pk)

        if locked_user.is_deleted:
            raise AccountAlreadyDeletedError()

        if locked_user.owned_workspaces.exists():
            raise AccountOwnsWorkspacesError()

        managed_roles = ProjectRole.objects.filter(
            user=locked_user,
            role__in=["ADMIN", "MANAGER"],
        ).select_related("project")

        orphaned_projects = []
        for role in managed_roles:
            has_replacement = ProjectRole.objects.filter(
                project=role.project,
                role__in=["ADMIN", "MANAGER"],
                user__is_deleted=False,
                user__is_active=True,
            ).exclude(user=locked_user).exists()
            if not has_replacement:
                orphaned_projects.append(role.project.name)

        if orphaned_projects:
            raise AccountIsLastProjectManagerError(orphaned_projects)

        unfinished_tasks = Task.objects.filter(
            assigned_to=locked_user,
            status__in=["TODO", "INPROGRESS", "REVIEW"],
        )
        unfinished_task_count = unfinished_tasks.update(
            assigned_to=None,
            assignment_state="UNASSIGNED_RETURNED",
        )

        active_bugs = BugReportForm.objects.filter(
            assigned_to=locked_user,
        ).exclude(status="CLOSED")
        unassigned_bug_count = active_bugs.update(assigned_to=None)

        project_memberships_removed, _ = ProjectRole.objects.filter(
            user=locked_user
        ).delete()
        workspace_memberships_removed, _ = WorkSpaceMember.objects.filter(
            user=locked_user
        ).delete()

        rejected_invitations = Invitation.objects.filter(
            Q(receiver=locked_user) | Q(receiver_email__iexact=locked_user.email),
            status="PENDING",
        ).update(status="REJECTED", receiver=locked_user)

        create_activity_log(
            user=locked_user,
            action="ACCOUNT_PURGED",
            action_id=locked_user.id,
            changes={
                "subject_name": locked_user.username,
                "reason": "Account soft-deleted by its owner.",
                "soft_delete": True,
                "unfinished_tasks_unassigned": unfinished_task_count,
                "active_bugs_unassigned": unassigned_bug_count,
                "project_memberships_removed": project_memberships_removed,
                "workspace_memberships_removed": workspace_memberships_removed,
                "pending_invitations_rejected": rejected_invitations,
            },
        )

        locked_user.soft_delete()

        return {
            "user_id": locked_user.id,
            "deleted": True,
            "unfinished_tasks_unassigned": unfinished_task_count,
            "active_bugs_unassigned": unassigned_bug_count,
            "pending_invitations_rejected": rejected_invitations,
        }
