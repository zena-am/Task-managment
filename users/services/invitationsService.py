from django.contrib.auth import get_user_model
from django.db import transaction
from users.constants import create_activity_log, create_notification
from users.errors.exceptions import (WorkspaceNotFound,ProjectNotFound,EmailAndWorkspaceRequired,ProjectIdRequired,InvitationAlreadyAccepted,InvitationForbidden,InvitationRejectForbidden)
from users.models import Invitation, WorkSpaceMember, WorkSpace, Project, ProjectRole
from users.serializers import invitation
from users.utils import notify_existing_user, notify_new_user


class InvitationService:
    @staticmethod
    def get_user_invitations(user):
        return Invitation.objects.filter(receiver_email=user.email)

    @staticmethod
    def send_workspace_invitation(sender, data):
        User = get_user_model()
        receiver_email = data.get("receiver_email")
        workspace = data.get("workspace")
        role = data.get("role", "EMPLOYEE")

        if not receiver_email or not workspace:
            raise EmailAndWorkspaceRequired()

        if isinstance(workspace, WorkSpace):
                workspace = workspace
        else:
                try:
                    workspace = WorkSpace.objects.get(id=workspace)
                except WorkSpace.DoesNotExist:
                    raise WorkspaceNotFound()
        sender_name = sender.get_full_name() or sender.username
        workspace_name = workspace.name

        existing_invitation = Invitation.objects.filter(receiver_email=receiver_email, workspace_id=workspace).first()

        if existing_invitation:
            if existing_invitation.status == "ACCEPTED":
                raise InvitationAlreadyAccepted()

            existing_invitation.status = "PENDING"
            existing_invitation.sender = sender
            existing_invitation.role = role
            existing_invitation.save()

            notify_existing_user(receiver_email, sender_name, workspace_name)

            return {
                "detail": "Invitation resent and updated.",
                "invitation": existing_invitation,
                "created": False,
            }

        receiver = User.objects.filter(email=receiver_email).first()

        invitation = Invitation.objects.create(
            sender=sender,
            receiver=receiver,
            receiver_email=receiver_email,
            workspace=workspace,
            role=role,
            status="PENDING",
        )

        if receiver:
            notify_existing_user(receiver_email, sender_name, workspace_name)
        else:
            notify_new_user(receiver_email, sender_name, workspace_name)

        create_activity_log(
            user=sender,
            action="INVITATION_SENT",
            action_id=invitation.id,
            subject_name=receiver_email,
            target_title=workspace.name,
            reason="New invitation sent"
        )

        if receiver:
            create_notification(
                recipient=receiver,
                notification_type="INVITATION_RECEIVED",
                title="New Invitation",
                message=f"{sender.username} invited you to {workspace.name}"
            )

        return {
            "detail": "Invitation sent successfully.",
            "invitation": invitation,
            "created": True,
        }



    @staticmethod
    def send_project_invitation(sender, data):
        User = get_user_model()

        project_id = data.get("project_id")
        if not project_id:
            raise ProjectIdRequired()

        try:
            project = Project.objects.get(id=project_id)
        except Project.DoesNotExist:
            raise ProjectNotFound()

        role = data.get("role", "DEV")
        member_emails = InvitationService._normalize_list(data.get("member_emails", []))
        members_ids = InvitationService._normalize_list(data.get("members_ids", []))

        added_members_count = InvitationService._add_existing_members_to_project(
            user_model=User,
            project=project,
            members_ids=members_ids,
            role=role,
        )

        invitations_count = InvitationService._send_project_email_invitations(
            user_model=User,
            sender=sender,
            project=project,
            member_emails=member_emails,
            role=role,
        )

        return {
            "detail": "Project invitations and additions processed successfully.",
            "added_members_count": added_members_count,
            "invitations_count": invitations_count,
        }




    @staticmethod
    def accept_invitation(invitation, user):
        if invitation.receiver_email != user.email:
            raise InvitationForbidden()

        with transaction.atomic():
            WorkSpaceMember.objects.get_or_create(
                workspace=invitation.workspace,
                user=user,
                defaults={"role": invitation.role},
            )

            if invitation.project:
                ProjectRole.objects.get_or_create(
                    project=invitation.project,
                    user=user,
                    defaults={"role": "DEV"},
                )

            invitation.receiver = user
            invitation.status = "ACCEPTED"
            invitation.save()
            create_activity_log(
                user=user,
                action="INVITATION_ACCEPTED",
                action_id=invitation.id,
                subject_name=user.username,
                target_title=invitation.workspace.name,
                reason="User accepted the invitation",
                is_by_admin=False
            )

            create_notification(
                recipient=invitation.sender,
                notification_type="INVITATION_ACCEPTED",
                title="Invitation Accepted",
                message=f"{user.username} has accepted your invitation to join {invitation.workspace.name}.",
                navigation_target=f"/workspaces/{invitation.workspace.id}"
            )

        return {
            "detail": "You have successfully joined the workspace/project."
        }

    @staticmethod
    def reject_invitation(invitation, user):
        if invitation.receiver_email != user.email:
            raise InvitationRejectForbidden()

        invitation.status = "REJECTED"
        invitation.receiver = user
        invitation.save()
        create_activity_log(
            user=user,
            action="INVITATION_REJECTED",
            action_id=invitation.id,
            subject_name=user.username,
            target_title=invitation.workspace.name,
            reason="User rejected the invitation"
        )

        create_notification(
            recipient=invitation.sender,
            notification_type="INVITATION_REJECTED",
            title="Invitation Rejected",
            message=f"{user.username} rejected your invitation to {invitation.workspace.name}."
        )

        return {
            "detail": "Invitation rejected successfully."
        }






    @staticmethod
    def _send_project_email_invitations(user_model, sender, project, member_emails, role):
        sender_name = sender.get_full_name() or sender.username
        workspace_name = project.workspace.name
        workspace = project.workspace
        invitations_count = 0

        for email in member_emails:
            existing_invitation = Invitation.objects.filter(receiver_email=email,workspace=workspace,project=project,).first()

            if existing_invitation:
                if existing_invitation.status == "ACCEPTED":
                    continue

                existing_invitation.status = "PENDING"
                existing_invitation.sender = sender
                existing_invitation.role = role
                existing_invitation.save()

                notify_existing_user(email, sender_name, workspace_name)
                invitations_count += 1
                continue

            receiver = user_model.objects.filter(email=email).first()

            create_activity_log(
                user=sender,
                action="INVITATION_SENT",
                action_id=invitation.id,
                subject_name=email,
                target_title=project.name,
                reason="Project invitation sent")

            if receiver:
                Invitation.objects.create(
                sender=sender,
                receiver=receiver,
                receiver_email=email,
                workspace=workspace,
                project=project,
                role=role,
                status="PENDING",
            )

                create_notification(
                    recipient=receiver,
                    notification_type="INVITATION_RECEIVED",
                    title="New Project Invitation",
                    message=f"{sender.username} invited you to {project.name}"
                )
                notify_existing_user(email, sender_name, workspace_name)
            else:
                Invitation.objects.create(
                sender=sender,
                receiver_email=email,
                project=project,
                workspace=project.workspace,
                role=role,
                status='PENDING')


                notify_new_user(email, sender_name, workspace_name)

            invitations_count += 1

        return invitations_count






    @staticmethod
    def _add_existing_members_to_project(user_model, project, members_ids, role):
        added_count = 0

        for user_id in members_ids:
            try:
                user_to_add = user_model.objects.get(id=user_id)
            except user_model.DoesNotExist:
                continue

            is_workspace_member = WorkSpaceMember.objects.filter(
                workspace=project.workspace,
                user=user_to_add,
            ).exists()

            if not is_workspace_member:
                continue

            WorkSpaceMember.objects.get_or_create(
                workspace=project.workspace,
                user=user_to_add,
                defaults={"role": "EMPLOYEE"},
            )

            _, created = ProjectRole.objects.get_or_create(
                project=project,
                user=user_to_add,
                defaults={"role": role},
            )

            if created:
                added_count += 1

        return added_count

    @staticmethod
    def _normalize_list(value):
        if not value:
            return []

        if isinstance(value, str):
            return [value]

        return value