from django.db.models import Case, When, Value, BooleanField
from django.shortcuts import get_object_or_404
from django.db import transaction
from users.errors.messages.success import success_response
from users.models import ProjectRole, Task, WorkSpace, WorkSpaceMember
from users.errors.exceptions import WorkspaceCannotLeaveAsCreator
from users.services.invitationsService import InvitationService


class WorkspaceServices:
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

        WorkSpaceMember.objects.get_or_create(user=user,
            workspace=workspace,
            defaults={
                "role": "ADMIN",
                "is_pinned":False
            }
        )

        invitations_result = WorkspaceServices._send_workspace_invitations(
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
        member_emails = serializer.validated_data.get("member_emails")
        workspace = serializer.save()
        invitations_result = None


        if member_emails:
            invitations_result = WorkspaceServices._send_workspace_invitations(
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

        with transaction.atomic():
            tasks = Task.objects.filter(
            assigned_to=user,
            project__workspace=workspace
        )

            if tasks.exists():
                tasks.update(
                    assigned_to=None,
                    status="UNASSIGNED"
                )

                ProjectRole.objects.filter(
                    project__workspace=workspace,
                    user=user
                ).delete()

                member.delete()

        return {
    "workspace_id": workspace.id
}

    def transfer_ownership(workspace, new_owner):
        old_owner = workspace.creator

        workspace.creator = new_owner
        workspace.save()

        WorkSpaceMember.objects.update_or_create(
            workspace=workspace,
            user=new_owner,
            defaults={"role": "ADMIN"}
        )

        WorkSpaceMember.objects.update_or_create(
            workspace=workspace,
            user=old_owner,
            defaults={"role": "MEMBER"}
        )
        return {
    "new_owner_id": new_owner.id
}






    @staticmethod
    def _send_workspace_invitations(sender, workspace, data):
        member_emails = WorkspaceServices._get_list_value(data, "member_emails")
        role = WorkspaceServices._get_value(data, "role") or "EMPLOYEE"

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

