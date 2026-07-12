from rest_framework.exceptions import APIException
from rest_framework import status

from users.errors.messages.ErrorCode import ErrorMessages


# =========================
# Base Exception
# =========================

class BaseAppException(APIException):
    status_code = 400
    default_detail = "Application error"
    default_code = "BUSINESS_ERROR"

    def __init__(self, detail=None, code=None, status_code=None):
        if status_code:
            self.status_code = status_code

        self.detail = {
            "message": detail or self.default_detail,
            "code": code or self.default_code
        }

# =========================
# USER / PROFILE
# =========================
class PhoneValidationError(BaseAppException):
    def __init__(self):
        super().__init__(
            detail=ErrorMessages.PHONE_VALIDATION_ERROR,
            code="PHONE_VALIDATION_ERROR",
            status_code=400
        )


class ProfileIncompleteError(BaseAppException):
    def __init__(self):
        super().__init__(
            detail=ErrorMessages.PROFILE_INCOMPLETE_ERROR,
            code="PROFILE_INCOMPLETE_ERROR",
            status_code=400
        )




class AccountAlreadyDeletedError(BaseAppException):
    def __init__(self):
        super().__init__(
            detail="This account has already been deleted.",
            code="ACCOUNT_ALREADY_DELETED",
            status_code=400,
        )


class AccountDeletedError(BaseAppException):
    def __init__(self):
        super().__init__(
            detail="This account has been deleted and cannot be used.",
            code="ACCOUNT_DELETED",
            status_code=403,
        )


class AccountOwnsWorkspacesError(BaseAppException):
    def __init__(self):
        super().__init__(
            detail="Transfer ownership of your workspaces before deleting your account.",
            code="ACCOUNT_OWNS_WORKSPACES",
            status_code=400,
        )


class AccountIsLastProjectManagerError(BaseAppException):
    def __init__(self, project_names=None):
        names = ", ".join(project_names or [])
        detail = "Assign another manager before deleting your account."
        if names:
            detail = f"Assign another manager for: {names}."
        super().__init__(
            detail=detail,
            code="ACCOUNT_IS_LAST_PROJECT_MANAGER",
            status_code=400,
        )


# =========================
# PERMISSIONS
# =========================
class PermissionDeniedError(BaseAppException):
    def __init__(self):
        super().__init__(
            detail=ErrorMessages.PERMISSION_DENIED,
            code="PERMISSION_DENIED",
            status_code=403
        )


class UserNotInProject(BaseAppException):
    def __init__(self):
        super().__init__(
            detail=ErrorMessages.USER_NOT_IN_PROJECT,
            code="USER_NOT_IN_PROJECT",
            status_code=403
        )


# =========================
# TASKS
# =========================
class TaskAlreadyCompleted(BaseAppException):
    def __init__(self):
        super().__init__(
            detail=ErrorMessages.TASK_ALREADY_COMPLETED,
            code="TASK_ALREADY_COMPLETED",
            status_code=400
        )


class TaskAlreadyAssigned(BaseAppException):
    def __init__(self):
        super().__init__(
            detail=ErrorMessages.TASK_ALREADY_ASSIGNED,
            code="TASK_ALREADY_ASSIGNED",
            status_code=400
        )


class TaskNotFound(BaseAppException):
    def __init__(self):
        super().__init__(
            detail=ErrorMessages.TASK_NOT_FOUND,
            code="TASK_NOT_FOUND",
            status_code=404
        )


class InvalidStatusError(BaseAppException):
    def __init__(self):
        super().__init__(
            detail=ErrorMessages.INVALID_STATUS,
            code="INVALID_STATUS",
            status_code=400
        )


class InvalidPriorityError(BaseAppException):
    def __init__(self):
        super().__init__(
            detail=ErrorMessages.INVALID_PRIORITY,
            code="INVALID_PRIORITY",
            status_code=400
        )


class TaskCannotRevertError(BaseAppException):
    def __init__(self):
        super().__init__(
            detail=ErrorMessages.TASK_CANNOT_REVERT,
            code="TASK_CANNOT_REVERT",
            status_code=400
        )


class TechnicalReportMissingError(BaseAppException):
    def __init__(self):
        super().__init__(
            detail=ErrorMessages.TECHNICAL_REPORT_MISSING,
            code="TECHNICAL_REPORT_MISSING",
            status_code=400
        )


# =========================
# WORKSPACE
# =========================
class WorkspaceAccessDenied(BaseAppException):
    def __init__(self):
        super().__init__(
            detail=ErrorMessages.WORKSPACE_ACCESS_DENIED,
            code="WORKSPACE_ACCESS_DENIED",
            status_code=403
        )


class WorkspaceCannotLeaveAsCreator(BaseAppException):
    def __init__(self):
        super().__init__(
            detail=ErrorMessages.WORKSPACE_CANNOT_LEAVE_AS_CREATOR,
            code="WORKSPACE_CANNOT_LEAVE_AS_CREATOR",
            status_code=400
        )


class WorkspaceMemberAlreadyExists(BaseAppException):
    def __init__(self):
        super().__init__(
            detail=ErrorMessages.WORKSPACE_MEMBER_ALREADY_EXISTS,
            code="WORKSPACE_MEMBER_ALREADY_EXISTS",
            status_code=400
        )


# =========================
# PROJECT
# =========================
class ProjectNotMember(BaseAppException):
    def __init__(self):
        super().__init__(
            detail=ErrorMessages.PROJECT_NOT_MEMBER,
            code="PROJECT_NOT_MEMBER",
            status_code=403
        )


class ProjectNotFound(BaseAppException):
    def __init__(self):
        super().__init__(
            detail=ErrorMessages.PROJECT_NOT_FOUND,
            code="PROJECT_NOT_FOUND",
            status_code=404
        )


# =========================
# WORKSPACE / INVITATIONS
# =========================
class WorkspaceNotFound(BaseAppException):
    def __init__(self):
        super().__init__(
            detail=ErrorMessages.WORKSPACE_NOT_FOUND,
            code="WORKSPACE_NOT_FOUND",
            status_code=404
        )


class EmailAndWorkspaceRequired(BaseAppException):
    def __init__(self):
        super().__init__(
            detail=ErrorMessages.EMAIL_REQUIRED,
            code="EMAIL_AND_WORKSPACE_REQUIRED",
            status_code=400
        )


class ProjectIdRequired(BaseAppException):
    def __init__(self):
        super().__init__(
            detail=ErrorMessages.PROJECT_ID_REQUIRED,
            code="PROJECT_ID_REQUIRED",
            status_code=400
        )


class InvitationAlreadyAccepted(BaseAppException):
    def __init__(self):
        super().__init__(
            detail=ErrorMessages.INVITATION_ALREADY_ACCEPTED,
            code="INVITATION_ALREADY_ACCEPTED",
            status_code=400
        )


class InvitationForbidden(BaseAppException):
    def __init__(self):
        super().__init__(
            detail=ErrorMessages.INVITATION_FORBIDDEN,
            code="INVITATION_FORBIDDEN",
            status_code=403
        )


class InvitationRejectForbidden(BaseAppException):
    def __init__(self):
        super().__init__(
            detail=ErrorMessages.INVITATION_REJECT_FORBIDDEN,
            code="INVITATION_REJECT_FORBIDDEN",
            status_code=403
        )


class InvitationNotFound(BaseAppException):
    def __init__(self):
        super().__init__(
            detail=ErrorMessages.INVITATION_NOT_FOUND,
            code="INVITATION_NOT_FOUND",
            status_code=404
        )

class ProjectInvitationError(BaseAppException):
    def __init__(self):
        super().__init__(
            detail=ErrorMessages.PROJECT_INVITATION_ERROR,
            code="PROJECT_INVITATION_ERROR",
            status_code=400
        )


class InvitationError(BaseAppException):
    def __init__(self):
        super().__init__(
            detail=ErrorMessages.INVITATION_FAILED,
            code="INVITATION_FAILED",
            status_code=400
        )
class UserNotFound(BaseAppException):
    def __init__(self):
        super().__init__(
            detail=ErrorMessages.USER_NOT_FOUND,
            code="USER_NOT_FOUND",
            status_code=404
        )


class ProjectAlreadyExists(BaseAppException):
    def __init__(self):
        super().__init__(
            detail=ErrorMessages.PROJECT_ALREADY_EXISTS,
            code="PROJECT_ALREADY_EXISTS",
            status_code=400
        )

class ProjectRoleNotFound(BaseAppException):
    def __init__(self):
        super().__init__(
            detail="Project role not found",
            code="PROJECT_ROLE_NOT_FOUND",
            status_code=404
        )

class RoleRequiredError(BaseAppException):
    def __init__(self):
        super().__init__(
            detail="Role is required",
            code="ROLE_REQUIRED",
            status_code=400
        )


class OnlyOneWorkspaceAdminError(BaseAppException):
    def __init__(self):
        super().__init__(
            detail="Only One  Admin in Workspace",
            code="OnlyOne_Workspace_Admin_Allowed",
            status_code=400
        )