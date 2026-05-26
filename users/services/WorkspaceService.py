from django.db.models import Case, When, Value, BooleanField
from django.shortcuts import get_object_or_404

from users.models import WorkSpace, WorkSpaceMember
from users.errors.exceptions import WorkspaceCannotLeaveAsCreator
from users.services.invitationsService import InvitationService


class WorkspaceService:
    @staticmethod
    def get_user_workspaces(user):
        return WorkSpace.objects.filter(members=user).annotate(
            user_pinned=Case(
                When(
                    workspacemember__user=user,
                    workspacemember__is_pinned=True,
                    then=Value(True)
                ),
                default=Value(False),
                output_field=BooleanField(),
            )
        ).order_by('-user_pinned', '-id').distinct()

    @staticmethod
    def create_workspace(serializer, user, data):
        workspace = serializer.save(creator=user)

        WorkSpaceMember.objects.get_or_create(
            user=user,
            workspace=workspace,
            defaults={
                "role": "ADMIN",
                "is_pinned": True
            }
        )

        invitations_result = WorkspaceService._send_workspace_invitations(
            sender=user,
            workspace=workspace,
            data=data
        )

        return {
            "workspace": workspace,
            "invitations_result": invitations_result
        }

    @staticmethod
    def update_workspace(serializer, user, data):
        workspace = serializer.save()

        invitations_result = WorkspaceService._send_workspace_invitations(
            sender=user,
            workspace=workspace,
            data=data
        )

        return {
            "workspace": workspace,
            "invitations_result": invitations_result
        }

    @staticmethod
    def toggle_pin(user, workspace):
        member_setting = get_object_or_404(
            WorkSpaceMember,
            user=user,
            workspace=workspace
        )

        member_setting.is_pinned = not member_setting.is_pinned
        member_setting.save()

        return {
            "message": "Workspace pin status updated successfully.",
            "is_pinned": member_setting.is_pinned
        }

    @staticmethod
    def leave_workspace(user, workspace):
        if workspace.creator == user:
            raise WorkspaceCannotLeaveAsCreator()

        member = get_object_or_404(
            WorkSpaceMember,
            user=user,
            workspace=workspace
        )

        member.delete()

        return {
            "message": f"You have successfully left the workspace: '{workspace.name}'."
        }

    @staticmethod
    def _send_workspace_invitations(sender, workspace, data):
        member_emails = WorkspaceService._get_list_value(data, "member_emails")
        role = WorkspaceService._get_value(data, "role") or "EMPLOYEE"

        results = []

        for email in member_emails:
            result = InvitationService.send_workspace_invitation(
                sender=sender,
                data={
                    "email": email,
                    "workspace_id": workspace.id,
                    "role": role
                }
            )
            results.append(result)

        return results

    @staticmethod
    def _get_value(data, key):
        if hasattr(data, "get"):
            return data.get(key)

        return None

    @staticmethod
    def _get_list_value(data, key):
        if hasattr(data, "getlist"):
            return data.getlist(key)

        value = data.get(key) if hasattr(data, "get") else None

        if not value:
            return []

        if isinstance(value, list):
            return value

        return [value]