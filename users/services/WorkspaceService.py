from users.models import Invitation, User, WorkSpaceMember
from users.utils import notify_existing_user, notify_new_user
from users.views.invitations import InvitationViewSet


class WorkspaceService:

    @staticmethod
    def create_workspace(serializer, user, data):
        workspace = serializer.save(creator=user)

        WorkSpaceMember.objects.get_or_create(
            user=user,
            workspace=workspace,
            role='ADMIN',
            defaults={'is_pinned': True}
        )

        member_emails = data.get('member_emails', [])
        if isinstance(member_emails, str):
            member_emails = [member_emails]

        WorkspaceService._handle_invitations(
            workspace=workspace,
            sender=user,
            emails=member_emails,
            role=data.get('role', 'DEV')
        )

        return workspace


    @staticmethod
    def _handle_invitations(workspace, sender, emails, role):
        sender_name = sender.get_full_name() or sender.username

        for email in emails:

            existing = Invitation.objects.filter(
                receiver_email=email,
                workspace=workspace
            ).first()

            if existing:
                if existing.status == 'ACCEPTED':
                    continue

                existing.status = 'PENDING'
                existing.sender = sender
                existing.role = role
                existing.save()

                notify_existing_user(email, sender_name, workspace.name)
                continue

            user = User.objects.filter(email=email).first()

            if user:
                Invitation.objects.create(
                    sender=sender,
                    receiver=user,
                    receiver_email=email,
                    workspace=workspace,
                    role=role,
                    status='PENDING'
                )
                notify_existing_user(email, sender_name, workspace.name)

            else:
                Invitation.objects.create(
                    sender=sender,
                    receiver_email=email,
                    workspace=workspace,
                    role=role,
                    status='PENDING'
                )
                notify_new_user(email, sender_name, workspace.name)