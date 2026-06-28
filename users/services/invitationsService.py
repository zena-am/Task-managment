from django.contrib.auth import get_user_model
from django.db import transaction

from users.constants import create_activity_log, create_notification
from users.errors.exceptions import (
    EmailAndWorkspaceRequired,
    InvitationAlreadyAccepted,
    InvitationForbidden,
    InvitationRejectForbidden,
    ProjectIdRequired,
    ProjectNotFound,
    WorkspaceNotFound,
)
from users.models import Invitation, WorkSpaceMember, WorkSpace, Project, ProjectRole
from users.utils import notify_existing_user, notify_new_user


class InvitationService:
    PROJECT_ROLES = {"ADMIN", "MANAGER", "EMPLOYEE"}
    WORKSPACE_ROLES = {"ADMIN", "MEMBER"}

    @staticmethod
    def get_user_invitations(user):
        return Invitation.objects.filter(receiver_email=user.email)

    @staticmethod
    def _normalize_list(value):
        if not value:
            return []
        if isinstance(value, str):
            return [value]
        return list(value)

    @staticmethod
    def _normalize_email_items(data):
        email_items = (
            data.get("receiver_emails")
            or data.get("member_emails")
            or data.get("emails")
            or []
        )
        email_items = InvitationService._normalize_list(email_items)

        single_email = data.get("receiver_email") or data.get("email")
        if single_email:
            email_items.append(single_email)

        normalized = []
        for item in email_items:
            if isinstance(item, dict):
                normalized.append({
                    "email": item.get("email") or item.get("receiver_email"),
                    "role": item.get("role"),
                })
            else:
                normalized.append({"email": item, "role": None})
        return normalized

    @staticmethod
    def _workspace_role(role):
        return "ADMIN" if role == "ADMIN" else "MEMBER"

    @staticmethod
    def _project_role(role):
        role = role or "EMPLOYEE"
        return role if role in InvitationService.PROJECT_ROLES else "EMPLOYEE"

    @staticmethod
    def _get_workspace(workspace_value):
        if isinstance(workspace_value, WorkSpace):
            return workspace_value
        if not workspace_value:
            raise EmailAndWorkspaceRequired()
        try:
            return WorkSpace.objects.get(id=workspace_value)
        except WorkSpace.DoesNotExist:
            raise WorkspaceNotFound()

    @staticmethod
    def _get_project(project_id):
        if not project_id:
            raise ProjectIdRequired()
        try:
            return Project.objects.select_related("workspace").get(id=project_id)
        except Project.DoesNotExist:
            raise ProjectNotFound()

    @staticmethod
    def _send_email(email, receiver, sender_name, workspace_name):
        if receiver:
            notify_existing_user(email, sender_name, workspace_name)
        else:
            notify_new_user(email, sender_name, workspace_name)

    @staticmethod
    def send_workspace_invitation(sender, data):
        User = get_user_model()
        workspace = InvitationService._get_workspace(data.get("workspace") or data.get("workspace_id"))
        email_items = InvitationService._normalize_email_items(data)

        if not email_items:
            raise EmailAndWorkspaceRequired()

        sender_name = sender.get_full_name() or sender.username
        workspace_name = workspace.name
        success_list = []
        error_list = []

        for item in email_items:
            email = item.get("email")
            role = InvitationService._workspace_role(item.get("role") or data.get("role") or "MEMBER")

            if not email:
                error_list.append({
                    "type": "INVALID_EMAIL",
                    "email": None,
                    "message": "Email is required",
                    "code": "INVALID_EMAIL",
                })
                continue

            receiver = User.objects.filter(email=email).first()
            existing_invitation = Invitation.objects.filter(
                receiver_email=email,
                workspace=workspace,
                project__isnull=True,
            ).first()

            if existing_invitation:
                if existing_invitation.status == "ACCEPTED":
                    error_list.append({
                        "type": "ALREADY_ACCEPTED",
                        "email": email,
                        "message": "Invitation already accepted",
                        "code": "INVITATION_ALREADY_ACCEPTED",
                    })
                    continue

                existing_invitation.status = "PENDING"
                existing_invitation.sender = sender
                existing_invitation.receiver = receiver
                existing_invitation.role = role
                existing_invitation.save(update_fields=["status", "sender", "receiver", "role", "updated_at"])
                invitation = existing_invitation
                result_type = "INVITATION_RESENT"
                result_code = "INVITATION_RESENT_SUCCESS"
            else:
                invitation = Invitation.objects.create(
                    sender=sender,
                    receiver=receiver,
                    receiver_email=email,
                    workspace=workspace,
                    project=None,
                    role=role,
                    status="PENDING",
                )
                result_type = "INVITATION_CREATED"
                result_code = "INVITATION_CREATED_SUCCESS"

            InvitationService._send_email(email, receiver, sender_name, workspace_name)
            create_activity_log(
                user=sender,
                action="INVITATION_SENT",
                action_id=invitation.id,
                subject_name=email,
                target_title=workspace.name,
                reason="Workspace invitation sent",
                is_by_admin=True,
            )
            if receiver:
                create_notification(
                    recipient=receiver,
                    notification_type="INVITATION_RECEIVED",
                    title="New Workspace Invitation",
                    message=f"{sender.username} invited you to join {workspace.name}.",
                    navigation_target=f"/workspaces/{workspace.id}",
                )

            success_list.append({
                "type": result_type,
                "email": email,
                "invitation_id": invitation.id,
                "role": role,
                "code": result_code,
            })

        return {"success": success_list, "errors": error_list}

    @staticmethod
    def send_project_invitation(sender, data):
        User = get_user_model()
        project = InvitationService._get_project(data.get("project_id") or data.get("project"))
        role = InvitationService._project_role(data.get("role"))
        email_items = InvitationService._normalize_email_items(data)
        members_ids = InvitationService._normalize_list(data.get("members_ids"))

        sender_name = sender.get_full_name() or sender.username
        workspace_name = project.workspace.name
        success_list = []
        error_list = []

        with transaction.atomic():
            for member in members_ids:
                if isinstance(member, dict):
                    user_id = member.get("id") or member.get("user_id")
                    user_role = InvitationService._project_role(member.get("role") or role)
                else:
                    user_id = member
                    user_role = role

                try:
                    user_to_add = User.objects.get(id=user_id)
                except User.DoesNotExist:
                    error_list.append({
                        "type": "USER_NOT_FOUND",
                        "id": user_id,
                        "message": "User not found",
                        "code": "USER_NOT_FOUND",
                        "status_code": 404,
                    })
                    continue

                WorkSpaceMember.objects.get_or_create(
                    workspace=project.workspace,
                    user=user_to_add,
                    defaults={"role": InvitationService._workspace_role(user_role)},
                )
                project_role, created = ProjectRole.objects.get_or_create(
                    project=project,
                    user=user_to_add,
                    defaults={"role": user_role},
                )
                if not created and project_role.role != user_role:
                    project_role.role = user_role
                    project_role.save(update_fields=["role"])

                create_notification(
                    recipient=user_to_add,
                    notification_type="SYSTEM_ALERT",
                    title="Project Access Updated",
                    message=f"You were added to project '{project.name}' as {user_role}.",
                    navigation_target=f"/projects/{project.id}",
                )

                success_list.append({
                    "type": "USER_ADDED",
                    "id": user_id,
                    "role": user_role,
                    "message": "User added successfully",
                    "code": "USER_ADDED_SUCCESS",
                })

            for item in email_items:
                email = item.get("email")
                item_role = InvitationService._project_role(item.get("role") or role)

                if not email:
                    error_list.append({
                        "type": "INVALID_EMAIL",
                        "email": None,
                        "message": "Email is required",
                        "code": "INVALID_EMAIL",
                    })
                    continue

                receiver = User.objects.filter(email=email).first()
                existing_invitation = Invitation.objects.filter(
                    receiver_email=email,
                    workspace=project.workspace,
                    project=project,
                ).first()

                if existing_invitation:
                    if existing_invitation.status == "ACCEPTED":
                        error_list.append({
                            "type": "ALREADY_ACCEPTED",
                            "email": email,
                            "message": "Invitation already accepted",
                            "code": "INVITATION_ALREADY_ACCEPTED",
                        })
                        continue

                    existing_invitation.status = "PENDING"
                    existing_invitation.sender = sender
                    existing_invitation.receiver = receiver
                    existing_invitation.role = item_role
                    existing_invitation.save(update_fields=["status", "sender", "receiver", "role", "updated_at"])
                    invitation = existing_invitation
                    result_type = "INVITATION_RESENT"
                    result_code = "INVITATION_RESENT_SUCCESS"
                else:
                    invitation = Invitation.objects.create(
                        sender=sender,
                        receiver=receiver,
                        receiver_email=email,
                        workspace=project.workspace,
                        project=project,
                        role=item_role,
                        status="PENDING",
                    )
                    result_type = "INVITATION_SENT"
                    result_code = "INVITATION_SENT_SUCCESS"

                InvitationService._send_email(email, receiver, sender_name, workspace_name)
                create_activity_log(
                    user=sender,
                    action="INVITATION_SENT",
                    action_id=invitation.id,
                    subject_name=email,
                    target_title=project.name,
                    reason="Project invitation sent",
                    is_by_admin=True,
                )
                if receiver:
                    create_notification(
                        recipient=receiver,
                        notification_type="INVITATION_RECEIVED",
                        title="New Project Invitation",
                        message=f"{sender.username} invited you to project {project.name}.",
                        navigation_target=f"/projects/{project.id}",
                    )

                success_list.append({
                    "type": result_type,
                    "email": email,
                    "invitation_id": invitation.id,
                    "role": item_role,
                    "message": "Invitation processed successfully",
                    "code": result_code,
                })

        return {"success": success_list, "errors": error_list}

    @staticmethod
    def accept_invitation(invitation, user):
        if invitation.receiver_email != user.email:
            raise InvitationForbidden()

        with transaction.atomic():
            WorkSpaceMember.objects.get_or_create(
                workspace=invitation.workspace,
                user=user,
                defaults={"role": InvitationService._workspace_role(invitation.role)},
            )

            if invitation.project:
                ProjectRole.objects.get_or_create(
                    project=invitation.project,
                    user=user,
                    defaults={"role": InvitationService._project_role(invitation.role)},
                )

            invitation.receiver = user
            invitation.status = "ACCEPTED"
            invitation.save(update_fields=["receiver", "status", "updated_at"])

            create_activity_log(
                user=user,
                action="INVITATION_ACCEPTED",
                action_id=invitation.id,
                subject_name=user.username,
                target_title=invitation.workspace.name,
                reason="User accepted the invitation",
                is_by_admin=False,
            )
            create_notification(
                recipient=invitation.sender,
                notification_type="INVITATION_ACCEPTED",
                title="Invitation Accepted",
                message=f"{user.username} accepted your invitation to {invitation.workspace.name}.",
                navigation_target=f"/workspaces/{invitation.workspace.id}",
            )

        return {"invitation_id": invitation.id, "status": "ACCEPTED"}

    @staticmethod
    def reject_invitation(invitation, user):
        if invitation.receiver_email != user.email:
            raise InvitationRejectForbidden()

        invitation.status = "REJECTED"
        invitation.receiver = user
        invitation.save(update_fields=["status", "receiver", "updated_at"])

        create_activity_log(
            user=user,
            action="INVITATION_REJECTED",
            action_id=invitation.id,
            subject_name=user.username,
            target_title=invitation.workspace.name,
            reason="User rejected the invitation",
            is_by_admin=False,
        )
        create_notification(
            recipient=invitation.sender,
            notification_type="INVITATION_REJECTED",
            title="Invitation Rejected",
            message=f"{user.username} rejected your invitation to {invitation.workspace.name}.",
            navigation_target=f"/workspaces/{invitation.workspace.id}",
        )

        return {"invitation_id": invitation.id, "status": "REJECTED"}
