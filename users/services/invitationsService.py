from django.contrib.auth import get_user_model
from django.db import transaction
from users.constants import create_activity_log, create_notification
from users.errors.exceptions import (BaseAppException,ProjectInvitationError,WorkspaceNotFound,ProjectNotFound,EmailAndWorkspaceRequired,ProjectIdRequired,InvitationAlreadyAccepted,InvitationForbidden,InvitationRejectForbidden)
from users.models import Invitation, WorkSpaceMember, WorkSpace, Project, ProjectRole
from users.utils import notify_existing_user, notify_new_user

class InvitationService:
    @staticmethod
    def get_user_invitations(user):
        return Invitation.objects.filter(receiver_email=user.email)


class InvitationService:
    @staticmethod
    def send_workspace_invitation(sender, data):
        User = get_user_model()

        receiver_email = data.get("receiver_email")
        receiver_emails = data.get("receiver_emails")
        workspace = data.get("workspace")
        role = data.get("role", "EMPLOYEE")

        success_list = []
        error_list = []

        if not workspace:
            raise EmailAndWorkspaceRequired()

        if not isinstance(workspace, WorkSpace):
            try:
                workspace = WorkSpace.objects.get(id=workspace)
            except WorkSpace.DoesNotExist:
                raise WorkspaceNotFound()

        sender_name = sender.get_full_name() or sender.username
        workspace_name = workspace.name


        if receiver_emails:
            for item in receiver_emails:

                if isinstance(item, dict):
                    email = item.get("email")
                    item_role = item.get("role", "MEMBER")
                else:
                    email = item
                    item_role = "MEMBER"

                if not email:
                    error_list.append({
                        "type": "INVALID_EMAIL",
                        "email": None,
                        "message": "Email is required",
                        "code": "INVALID_EMAIL"
                    })
                    continue

                User = get_user_model()
                receiver = User.objects.filter(email=email).first()

                existing_invitation = Invitation.objects.filter(
                    receiver_email=email,
                    workspace=workspace
                ).first()

                if existing_invitation:
                    if existing_invitation.status == "ACCEPTED":
                        error_list.append({
                            "type": "ALREADY_ACCEPTED",
                            "email": email,
                            "code": "INVITATION_ALREADY_ACCEPTED"
                        })
                        continue

                    existing_invitation.status = "PENDING"
                    existing_invitation.sender = sender
                    existing_invitation.role = item_role
                    existing_invitation.save()

                    success_list.append({
                        "type": "INVITATION_RESENT",
                        "email": email,
                        "invitation_id": existing_invitation.id,
                        "role": item_role,
                        "code": "INVITATION_RESENT_SUCCESS"
                    })
                    continue

                invitation = Invitation.objects.create(
                    sender=sender,
                    receiver=receiver,
                    receiver_email=email,
                    workspace=workspace,
                    role=item_role,
                    status="PENDING",
                )

                success_list.append({
                    "type": "INVITATION_CREATED",
                    "email": email,
                    "invitation_id": invitation.id,
                    "role": item_role,
                    "code": "INVITATION_CREATED_SUCCESS"
                })

                if receiver:
                    notify_existing_user(email, sender_name, workspace_name)
                else:
                    notify_new_user(email, sender_name, workspace_name)

          
        if not receiver_email:
            raise EmailAndWorkspaceRequired()

        receiver = User.objects.filter(email=receiver_email).first()

        invitation = Invitation.objects.create(
            sender=sender,
            receiver=receiver,
            receiver_email=receiver_email,
            workspace=workspace,
            role=role,
            status="PENDING",
        )

        success_list.append({
            "type": "INVITATION_CREATED",
            "email": receiver_email,
            "invitation_id": invitation.id,
            "code": "INVITATION_CREATED_SUCCESS"
        })

        if receiver:
            notify_existing_user(receiver_email, sender_name, workspace_name)
        else:
            notify_new_user(receiver_email, sender_name, workspace_name)

        return {
    "success": success_list,
    "errors": error_list
}
###########################################
    """
    @staticmethod
    def send_workspace_invitation(sender, data):
        User = get_user_model()
        receiver_email = data.get("receiver_email")
        workspace = data.get("workspace")
        role = data.get("role", "EMPLOYEE")
        success_list = []
        error_list = []


        if not receiver_email or not workspace:
            raise EmailAndWorkspaceRequired()

        if not isinstance(workspace, WorkSpace):
            try:
                workspace = WorkSpace.objects.get(id=workspace)
            except WorkSpace.DoesNotExist:
                raise WorkspaceNotFound()
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

            return success_response(
            message="Invitation resent and updated.",
            code="INVITATION_RESENT_SUCCESS",
            data={
                "invitation_id": existing_invitation.id if existing_invitation else None
            }
)
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
            success_list.append({
    "type": "INVITATION_RESENT",
    "email": receiver_email,
    "invitation_id": existing_invitation.id,
    "message": "Invitation resent successfully",
    "code": "INVITATION_RESENT_SUCCESS"
})

        else:
            notify_new_user(receiver_email, sender_name, workspace_name)
            success_list.append({
    "type": "INVITATION_CREATED",
    "email": receiver_email,
    "invitation_id": invitation.id,
    "message": "Invitation created successfully",
    "code": "INVITATION_CREATED_SUCCESS"
})

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
    """
##################################################################333
    @staticmethod
    def send_project_invitation(sender, data):
        User = get_user_model()
        project_id = data.get('project_id')
        role = data.get('role', 'MEMBER')
        receiver_emails = data.get('receiver_emails', [])
        members_ids = data.get('members_ids', [])

        projects = Project.objects.select_related('workspace').all()
        if not project_id:
            raise ProjectIdRequired()

        try:
            project = Project.objects.select_related('workspace').get(id=project_id)
        except Project.DoesNotExist:
            raise ProjectNotFound()

        sender_name = sender.get_full_name() or sender.username
        workspace_name = project.workspace.name
        success_list = []
        error_list = []

        for member in members_ids:
            if isinstance(member, dict):
                user_id = member.get("id")
                user_role = member.get("role", "EMPLOYEE")
            else:
                user_id = member
                user_role = "EMPLOYEE"
            try:
                user_to_add = User.objects.get(id=user_id)

                workspace_member, _ = WorkSpaceMember.objects.get_or_create(
                    workspace=project.workspace, user=user_to_add,
                    defaults={'role': user_role}
                )
                ProjectRole.objects.get_or_create(
                    project=project, user=user_to_add, defaults={'role': user_role}
                )

                success_list.append({
                "type": "USER_ADDED",
                "id": user_id,
                "message": "User added successfully",
                "code": "USER_ADDED_SUCCESS"
            })


            except User.DoesNotExist:

                error_list.append({
    "type": "USER_NOT_FOUND",
    "id": user_id,
    "message": "User not found",
    "code": "USER_NOT_FOUND",
    "status_code": 404
})
                continue
        for item in receiver_emails:

            if isinstance(item, dict):
                    email = item.get("email")
                    item_role = item.get("role", "MEMBER")
            else:
                    email = item
                    item_role = "MEMBER"

            if not email:
                    error_list.append({
                        "type": "INVALID_EMAIL",
                        "email": None,
                        "message": "Email is required",
                        "code": "INVALID_EMAIL"
                    })
                    continue


            try:
                existing_invitation = Invitation.objects.filter(
                    receiver_email=email, workspace=project.workspace, project=project
                ).first()

                if existing_invitation and existing_invitation.status != 'ACCEPTED':
                    existing_invitation.status = 'PENDING'
                    existing_invitation.sender = sender
                    existing_invitation.role = role
                    existing_invitation.save()
                    notify_existing_user(email, sender_name, workspace_name)
                    success_list.append({
    "type": "INVITATION_RESENT",
    "email": email,
    "invitation_id": existing_invitation.id,
    "message": "Invitation resent successfully",
    "code": "INVITATION_RESENT_SUCCESS"
})
                else:
                    receiver = User.objects.filter(email=email).first()
                    invitation =  Invitation.objects.create(
                        sender=sender, receiver=receiver, receiver_email=email,
                        workspace=project.workspace, project=project, role=role, status='PENDING'
                    )

                    if receiver:
                        notify_existing_user(email, sender_name, workspace_name)
                        success_list.append({
    "type": "INVITATION_RESENT",
    "email": email,
    "invitation_id": invitation.id,
    "message": "Invitation resent successfully",
    "code": "INVITATION_RESENT_SUCCESS"
})
                    else:
                        notify_new_user(email, sender_name, workspace_name)
                        success_list.append({
    "type": "INVITATION_SENT",
    "email": email,
    "message": "Invitation sent successfully",
    "code": "INVITATION_SENT_SUCCESS"
})
            except Exception as e:
                    error_list.append({
    "type": "INVALID_EMAIL",
    "email": email,
    "message": "User not found for this email",
    "code": "USER_NOT_FOUND",
    "status_code": 404
})
        import inspect

        return {
    "success": success_list,
    "errors": error_list
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
                    defaults={"role": invitation.role},
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
    "invitation_id": invitation.id,
    "status": "ACCEPTED"
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
        "invitation_id": invitation.id,
        "status": "REJECTED"
    }





    @staticmethod
    def _send_project_email_invitations(user_model, sender, project, member_emails, role):
        sender_name = sender.get_full_name() or sender.username
        workspace_name = project.workspace.name
        workspace = project.workspace
        invitations_count = 0
        existing_invitation = Invitation.objects.filter(
    receiver_email=email,
    workspace=workspace,
    project=project
).first()

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
                action_id=existing_invitation.id,
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