from django.contrib.auth import get_user_model
from django.db import transaction
from django.core.exceptions import ValidationError
from django.core.validators import validate_email

from users.constants import create_activity_log, create_notification
from users.errors.exceptions import (
    BaseAppException,
    EmailAndWorkspaceRequired,
    InvitationForbidden,
    InvitationRejectForbidden,
    ProjectIdRequired,
    ProjectNotFound,
    WorkspaceNotFound,
)
from users.models import Invitation, Project, ProjectRole, WorkSpace, WorkSpaceMember
from users.services.user_availability_service import UserAvailabilityService
from users.utils import notify_existing_user, notify_new_user


class InvitationService:
    PROJECT_ROLES = {"ADMIN", "MANAGER", "EMPLOYEE"}
    WORKSPACE_ROLES = {"ADMIN", "MEMBER"}

    @staticmethod
    def get_user_invitations(user):
        return Invitation.objects.filter(receiver_email__iexact=user.email)

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
                email = item.get("email") or item.get("receiver_email")
                role = item.get("role")
            else:
                email, role = item, None
            normalized.append({
                "email": email.strip().lower() if isinstance(email, str) else email,
                "role": role,
            })
        deduplicated = []
        seen = set()
        for item in normalized:
            email = item.get("email")
            key = email.lower() if isinstance(email, str) else email
            if key in seen:
                continue
            seen.add(key)
            deduplicated.append(item)
        return deduplicated

    @staticmethod
    def _validate_email(email):
        if not isinstance(email, str) or not email.strip():
            return None, {
                "type": "INVALID_EMAIL",
                "email": email,
                "message": "Email is required",
                "code": "INVALID_EMAIL",
            }
        normalized = email.strip().lower()
        try:
            validate_email(normalized)
        except ValidationError:
            return None, {
                "type": "INVALID_EMAIL_FORMAT",
                "email": normalized,
                "message": "Invalid email format",
                "code": "INVALID_EMAIL_FORMAT",
            }
        return normalized, None

    @staticmethod
    def _self_invitation_error(sender, email):
        if sender.email and sender.email.strip().lower() == email:
            return {
                "type": "SELF_INVITATION_NOT_ALLOWED",
                "email": email,
                "message": "You cannot invite yourself",
                "code": "SELF_INVITATION_NOT_ALLOWED",
            }
        return None

    @staticmethod
    def _workspace_role(role):
        return "MEMBER"

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
    def _resolve_receiver(email):
        User = get_user_model()
        return User.all_objects.filter(email__iexact=email).first()

    @staticmethod
    def _unavailable_error(receiver, *, email=None, user_id=None):
        if not receiver:
            return None
        if receiver.is_deleted:
            return {
                "type": "USER_DELETED",
                "email": email,
                "id": user_id,
                "message": "This account has been deleted.",
                "code": "USER_DELETED",
            }
        if not receiver.is_active:
            return {
                "type": "USER_INACTIVE",
                "email": email,
                "id": user_id,
                "message": "This account is inactive.",
                "code": "USER_INACTIVE",
            }
        return None

    @staticmethod
    def _send_email(email, receiver, sender_name, workspace_name):
        if receiver:
            notify_existing_user(email, sender_name, workspace_name)
        else:
            notify_new_user(email, sender_name, workspace_name)

    @staticmethod
    def send_workspace_invitation(sender, data):
        workspace = InvitationService._get_workspace(
            data.get("workspace") or data.get("workspace_id")
        )

        can_invite = (
            workspace.creator_id == sender.id
            or WorkSpaceMember.objects.filter(
                workspace=workspace,
                user=sender,
                role="ADMIN",
            ).exists()
        )

        if not can_invite:
            raise BaseAppException(
                detail="You can only invite member to your own project.",
                code="PermissionDeniedError",
                status_code=403,
            )
        email_items = InvitationService._normalize_email_items(data)
        if not email_items:
            raise EmailAndWorkspaceRequired()

        sender_name = sender.get_full_name() or sender.username
        success_list, error_list = [], []

        for item in email_items:
            email = item.get("email")
            role = InvitationService._workspace_role(
                item.get("role") or data.get("role") or "MEMBER"
            ).upper()
            if role != "MEMBER":
                    error_list.append({
                        "type": "INVALID_WORKSPACE_ROLE",
                        "email": email,
                        "message": (
                            "Workspace invitations can only assign "
                            "the MEMBER role."
                        ),
                        "code": "WORKSPACE_INVITATION_MEMBER_ONLY",
                    })
                    continue

            role = "MEMBER"
            email, email_error = InvitationService._validate_email(email)
            if email_error:
                error_list.append(email_error)
                continue
            self_error = InvitationService._self_invitation_error(sender, email)
            if self_error:
                error_list.append(self_error)
                continue

            receiver = InvitationService._resolve_receiver(email)
            unavailable = InvitationService._unavailable_error(receiver, email=email)
            if unavailable:
                error_list.append(unavailable)
                continue

            if receiver and WorkSpaceMember.objects.filter(workspace=workspace, user=receiver).exists():
                error_list.append({
                    "type": "MEMBER_ALREADY_IN_WORKSPACE",
                    "email": email,
                    "message": "User is already a workspace member",
                    "code": "MEMBER_ALREADY_IN_WORKSPACE",
                })
                continue

            existing = Invitation.objects.filter(
                receiver_email__iexact=email, workspace=workspace, project__isnull=True
            ).first()
            if existing and existing.status == "ACCEPTED":
                error_list.append({
                    "type": "ALREADY_ACCEPTED",
                    "email": email,
                    "message": "Invitation already accepted",
                    "code": "INVITATION_ALREADY_ACCEPTED",
                })
                continue

            if existing:
                existing.status = "PENDING"
                existing.sender = sender
                existing.receiver = receiver
                existing.role = role
                existing.save(update_fields=["status", "sender", "receiver", "role", "updated_at"])
                invitation, result_type, result_code = existing, "INVITATION_RESENT", "INVITATION_RESENT_SUCCESS"
            else:
                invitation = Invitation.objects.create(
                    sender=sender, receiver=receiver, receiver_email=email,
                    workspace=workspace, project=None, role=role, status="PENDING"
                )
                result_type, result_code = "INVITATION_CREATED", "INVITATION_CREATED_SUCCESS"

            InvitationService._send_email(email, receiver, sender_name, workspace.name)
            create_activity_log(
                user=sender, action="INVITATION_SENT", action_id=invitation.id,
                subject_name=email, target_title=workspace.name,
                reason="Workspace invitation sent", is_by_admin=True,
            )
            if receiver:
                create_notification(
                    recipient=receiver, notification_type="INVITATION_RECEIVED",
                    title="New Workspace Invitation",
                    message=f"{sender.username} invited you to join {workspace.name}.",
                    navigation_target=f"/workspaces/{workspace.id}",
                )
            success_list.append({
                "type": result_type, "email": email, "invitation_id": invitation.id,
                "role": role, "code": result_code,
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
        success_list, error_list = [], []
        can_invite = ProjectRole.objects.filter(
            project=project,
            user=sender,
            role__in=["ADMIN", "MANAGER"],
        ).exists()


        is_workspace_admin = (
            project.workspace.creator_id == sender.id
            or WorkSpaceMember.objects.filter(
                workspace=project.workspace,
                user=sender,
                role="ADMIN",
            ).exists()
        )

        sender_role = ProjectRole.objects.filter(
                project=project,
                user=sender,
            ).values_list(
                "role",
                flat=True,
            ).first()

        is_project_admin = sender_role == "ADMIN"
        is_project_manager = sender_role == "MANAGER"

        can_invite = (
                is_workspace_admin
                or is_project_admin
                or is_project_manager
            )

        if not can_invite:
                raise BaseAppException(
                    detail=(
                        "You are not allowed to invite members "
                        "to this project."
                    ),
                    code="PROJECT_INVITATION_FORBIDDEN",
                    status_code=403,
                )


        with transaction.atomic():
            for member in members_ids:
                if isinstance(member, dict):
                    user_id = member.get("id") or member.get("user_id")
                    user_role = InvitationService._project_role(member.get("role") or role)
                else:
                    user_id, user_role = member, role
                if (
                    is_project_manager
                        and not is_workspace_admin
                        and not is_project_admin
                        and user_role != "EMPLOYEE"
                    ):
                        raise BaseAppException(
                            detail=(
                                "Project managers can only invite employees."
                            ),
                            code="MANAGER_CAN_INVITE_EMPLOYEE_ONLY",
                            status_code=403,
                        )


                user_to_add = User.all_objects.filter(id=user_id).first()
                if not user_to_add:
                    error_list.append({
                        "type": "USER_NOT_FOUND", "id": user_id,
                        "message": "User not found", "code": "USER_NOT_FOUND",
                    })
                    continue
                unavailable = InvitationService._unavailable_error(user_to_add, user_id=user_id)
                if unavailable:
                    error_list.append(unavailable)
                    continue
                if user_to_add.id == sender.id:
                    error_list.append({
                        "type": "SELF_INVITATION_NOT_ALLOWED", "id": user_id,
                        "message": "You cannot add yourself through invitations",
                        "code": "SELF_INVITATION_NOT_ALLOWED",
                    })
                    continue

                existing_project_role = ProjectRole.objects.filter(project=project, user=user_to_add).first()
                if existing_project_role and existing_project_role.role == user_role:
                    error_list.append({
                        "type": "MEMBER_ALREADY_IN_PROJECT", "id": user_id,
                        "message": "User is already a project member with this role",
                        "code": "MEMBER_ALREADY_IN_PROJECT",
                    })
                    continue

                WorkSpaceMember.objects.get_or_create(
                    workspace=project.workspace, user=user_to_add,
                    defaults={"role": InvitationService._workspace_role(user_role)},
                )
                project_role, created = ProjectRole.objects.get_or_create(
                    project=project, user=user_to_add, defaults={"role": user_role}
                )
                if not created:
                    error_list.append({
                        "type": "MEMBER_ALREADY_IN_PROJECT", "id": user_id,
                        "message": "User is already a project member; use the role update endpoint",
                        "code": "MEMBER_ALREADY_IN_PROJECT",
                    })
                    continue

                create_activity_log(
                    user=sender, action="MEMBER_ADDED", action_id=project.id,
                    subject_name=user_to_add.username, target_title=project.name,
                    reason=f"User added to project as {user_role}", is_by_admin=True,
                )
                create_notification(
                    recipient=user_to_add, notification_type="SYSTEM_ALERT",
                    title="Project Access Updated",
                    message=f"You were added to project '{project.name}' as {user_role}.",
                    navigation_target=f"/projects/{project.id}",
                )
                success_list.append({
                    "type": "USER_ADDED", "id": user_id, "role": user_role,
                    "message": "User added successfully", "code": "USER_ADDED_SUCCESS",
                })

            for item in email_items:
                email = item.get("email")
                item_role = InvitationService._project_role(item.get("role") or role)
                if (
                    is_project_manager
                    and not is_workspace_admin
                    and not is_project_admin
                    and item_role != "EMPLOYEE"
                ):
                    raise BaseAppException(
                        detail=(
                            "Project managers can only invite employees."
                        ),
                        code="MANAGER_CAN_INVITE_EMPLOYEE_ONLY",
                        status_code=403,
                    )
                email, email_error = InvitationService._validate_email(email)
                if email_error:
                    error_list.append(email_error)
                    continue
                self_error = InvitationService._self_invitation_error(sender, email)
                if self_error:
                    error_list.append(self_error)
                    continue

                receiver = InvitationService._resolve_receiver(email)
                unavailable = InvitationService._unavailable_error(receiver, email=email)
                if unavailable:
                    error_list.append(unavailable)
                    continue

                if receiver and ProjectRole.objects.filter(project=project, user=receiver).exists():
                    error_list.append({
                        "type": "MEMBER_ALREADY_IN_PROJECT",
                        "email": email,
                        "message": "User is already a project member",
                        "code": "MEMBER_ALREADY_IN_PROJECT",
                    })
                    continue

                existing = Invitation.objects.filter(
                    receiver_email__iexact=email, workspace=project.workspace, project=project
                ).first()
                if existing and existing.status == "ACCEPTED":
                    error_list.append({
                        "type": "ALREADY_ACCEPTED", "email": email,
                        "message": "Invitation already accepted",
                        "code": "INVITATION_ALREADY_ACCEPTED",
                    })
                    continue

                if existing:
                    existing.status = "PENDING"
                    existing.sender = sender
                    existing.receiver = receiver
                    existing.role = item_role
                    existing.save(update_fields=["status", "sender", "receiver", "role", "updated_at"])
                    invitation, result_type, result_code = existing, "INVITATION_RESENT", "INVITATION_RESENT_SUCCESS"
                else:
                    invitation = Invitation.objects.create(
                        sender=sender, receiver=receiver, receiver_email=email,
                        workspace=project.workspace, project=project, role=item_role, status="PENDING"
                    )
                    result_type, result_code = "INVITATION_SENT", "INVITATION_SENT_SUCCESS"

                InvitationService._send_email(email, receiver, sender_name, project.workspace.name)
                create_activity_log(
                    user=sender, action="INVITATION_SENT", action_id=invitation.id,
                    subject_name=email, target_title=project.name,
                    reason="Project invitation sent", is_by_admin=True,
                )
                if receiver:
                    create_notification(
                        recipient=receiver, notification_type="INVITATION_RECEIVED",
                        title="New Project Invitation",
                        message=f"{sender.username} invited you to project {project.name}.",
                        navigation_target=f"/projects/{project.id}",
                    )
                success_list.append({
                    "type": result_type, "email": email, "invitation_id": invitation.id,
                    "role": item_role, "message": "Invitation processed successfully",
                    "code": result_code,
                })

        return {"success": success_list, "errors": error_list}

    @staticmethod
    def accept_invitation(invitation, user):
        UserAvailabilityService.ensure_active(user, action="invitation acceptance")
        if invitation.receiver_email.lower() != user.email.lower():
            raise InvitationForbidden()

        with transaction.atomic():
            WorkSpaceMember.objects.get_or_create(
                workspace=invitation.workspace, user=user,
                defaults={"role": InvitationService._workspace_role(invitation.role)},
            )
            if invitation.project:
                ProjectRole.objects.get_or_create(
                    project=invitation.project, user=user,
                    defaults={"role": InvitationService._project_role(invitation.role)},
                )
            invitation.receiver = user
            invitation.status = "ACCEPTED"
            invitation.save(update_fields=["receiver", "status", "updated_at"])

            create_activity_log(
                user=user, action="INVITATION_ACCEPTED", action_id=invitation.id,
                subject_name=user.username, target_title=invitation.workspace.name,
                reason="User accepted the invitation", is_by_admin=False,
            )
            if invitation.sender_id != user.id:
                create_notification(
                    recipient=invitation.sender, notification_type="INVITATION_ACCEPTED",
                    title="Invitation Accepted",
                    message=f"{user.username} accepted your invitation to {invitation.workspace.name}.",
                    navigation_target=f"/workspaces/{invitation.workspace.id}",
                )
        return {"invitation_id": invitation.id, "status": "ACCEPTED"}

    @staticmethod
    def reject_invitation(invitation, user):
        UserAvailabilityService.ensure_active(user, action="invitation rejection")
        if invitation.receiver_email.lower() != user.email.lower():
            raise InvitationRejectForbidden()

        invitation.status = "REJECTED"
        invitation.receiver = user
        invitation.save(update_fields=["status", "receiver", "updated_at"])
        create_activity_log(
            user=user, action="INVITATION_REJECTED", action_id=invitation.id,
            subject_name=user.username, target_title=invitation.workspace.name,
            reason="User rejected the invitation", is_by_admin=False,
        )
        if invitation.sender_id != user.id:
            create_notification(
                recipient=invitation.sender, notification_type="INVITATION_REJECTED",
                title="Invitation Rejected",
                message=f"{user.username} rejected your invitation to {invitation.workspace.name}.",
                navigation_target=f"/workspaces/{invitation.workspace.id}",
            )
        return {"invitation_id": invitation.id, "status": "REJECTED"}
