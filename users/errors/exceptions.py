from rest_framework.exceptions import APIException
from rest_framework import status
from users.errors.messages.errorsMessages import ErrorMessages



class BaseAppException(APIException):
    code = "ERROR"
    message = ErrorMessages.INVALID_OPERATION
    status_code = status.HTTP_400_BAD_REQUEST

    def __init__(self, detail=None):
        if detail is None:
            detail = {
                "code": self.code,
                "message": self.message
            }
        super().__init__(detail=detail)



class PhoneValidationError(BaseAppException):
    code = "PHONE_VALIDATION_ERROR"
    message = ErrorMessages.PHONE_VALIDATION_ERROR
    status_code = status.HTTP_400_BAD_REQUEST


class ProfileIncompleteError(BaseAppException):
    code = "PROFILE_INCOMPLETE_ERROR"
    message = ErrorMessages.PROFILE_INCOMPLETE_ERROR
    status_code = status.HTTP_400_BAD_REQUEST

class PermissionDeniedError(BaseAppException):
    code = "PERMISSION_DENIED"
    message = ErrorMessages.PERMISSION_DENIED
    status_code = status.HTTP_403_FORBIDDEN


class UserNotInProject(BaseAppException):
    code = "USER_NOT_IN_PROJECT"
    message = ErrorMessages.USER_NOT_IN_PROJECT
    status_code = status.HTTP_403_FORBIDDEN

#task


class TaskAlreadyAssigned(BaseAppException):
    code = "TASK_ALREADY_ASSIGNED"
    message = ErrorMessages.TASK_ALREADY_ASSIGNED
    status_code = status.HTTP_400_BAD_REQUEST


class TaskNotFound(BaseAppException):
    code = "TASK_NOT_FOUND"
    message = ErrorMessages.TASK_NOT_FOUND
    status_code = status.HTTP_404_NOT_FOUND


class InvalidStatusError(BaseAppException):
    code = "INVALID_STATUS"
    message = ErrorMessages.INVALID_STATUS
    status_code = status.HTTP_400_BAD_REQUEST


class InvalidPriorityError(BaseAppException):
    code = "INVALID_PRIORITY"
    message = ErrorMessages.INVALID_PRIORITY
    status_code = status.HTTP_400_BAD_REQUEST


class TaskCannotRevertError(BaseAppException):
    code = "TASK_CANNOT_REVERT"
    message = ErrorMessages.TASK_CANNOT_REVERT
    status_code = status.HTTP_400_BAD_REQUEST

class TechnicalReportMissingError(BaseAppException):
    code = "Technical_Report_Missing"
    message = ErrorMessages.TechnicalReportMissingError
    status_code = status.HTTP_400_BAD_REQUEST
#workspace
class WorkspaceAccessDenied(BaseAppException):
    code = "WORKSPACE_ACCESS_DENIED"
    message = ErrorMessages.WORKSPACE_ACCESS_DENIED
    status_code = status.HTTP_403_FORBIDDEN


class WorkspaceCannotLeaveAsCreator(BaseAppException):
    code = "WORKSPACE_CANNOT_LEAVE_AS_CREATOR"
    message = ErrorMessages.WORKSPACE_CANNOT_LEAVE_AS_CREATOR
    status_code = status.HTTP_400_BAD_REQUEST


#project
class ProjectNotMember(BaseAppException):
    code = "PROJECT_NOT_MEMBER"
    message = ErrorMessages.PROJECT_NOT_MEMBER
    status_code = status.HTTP_403_FORBIDDEN

#invitation
class WorkspaceNotFound(BaseAppException):
    code = "WORKSPACE_NOT_FOUND"
    message = ErrorMessages.WORKSPACE_NOT_FOUND
    status_code = status.HTTP_404_NOT_FOUND


class ProjectNotFound(BaseAppException):
    code = "PROJECT_NOT_FOUND"
    message = ErrorMessages.PROJECT_NOT_FOUND
    status_code = status.HTTP_404_NOT_FOUND


class EmailAndWorkspaceRequired(BaseAppException):
    code = "EMAIL_AND_WORKSPACE_REQUIRED"
    message = ErrorMessages.EMAIL_REQUIRED
    status_code = status.HTTP_400_BAD_REQUEST


class ProjectIdRequired(BaseAppException):
    code = "PROJECT_ID_REQUIRED"
    message = ErrorMessages.PROJECT_ID_REQUIRED
    status_code = status.HTTP_400_BAD_REQUEST


class InvitationAlreadyAccepted(BaseAppException):
    code = "INVITATION_ALREADY_ACCEPTED"
    message = ErrorMessages.INVITATION_ALREADY_ACCEPTED
    status_code = status.HTTP_400_BAD_REQUEST


class InvitationForbidden(BaseAppException):
    code = "INVITATION_FORBIDDEN"
    message = ErrorMessages.INVITATION_FORBIDDEN
    status_code = status.HTTP_403_FORBIDDEN


class InvitationRejectForbidden(BaseAppException):
    code = "INVITATION_REJECT_FORBIDDEN"
    message = ErrorMessages.INVITATION_REJECT_FORBIDDEN
    status_code = status.HTTP_403_FORBIDDEN


class WorkspaceMemberAlreadyExists(BaseAppException):
    code = "WORKSPACE_MEMBER_ALREADY_EXISTS"
    message = ErrorMessages.WORKSPACE_MEMBER_ALREADY_EXISTS
    status_code = status.HTTP_400_BAD_REQUEST



class InvitationNotFound(BaseAppException):
    code = "INVITATION_NOT_FOUND"
    message = ErrorMessages.INVITATION_NOT_FOUND
    status_code = status.HTTP_404_NOT_FOUND


