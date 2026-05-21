from rest_framework.exceptions import APIException
from rest_framework import status

class ErrorMessages:
    # User
    PHONE_VALIDATION_ERROR = (
        "Please enter a valid phone number in international format "
        "(e.g., '+9665xxxxxxxx' or without '+'). Only 9 to 15 digits are allowed."
    )

    PROFILE_INCOMPLETE_ERROR = (
        "Please complete your profile details (avatar and phone) "
        "before creating or managing projects."
    )

    # Workspace
    INVALID_WORKSPACE_EMAIL = (
        "The email address is invalid. It must end with .com, .org, .net, or .edu"
    )

    WORKSPACE_ACCESS_DENIED = (
        "You cannot create or manage a project in a workspace you are not a member of."
    )
    WORKSPACE_CANNOT_LEAVE_AS_CREATOR = "As the creator, you cannot leave this workspace. You must delete it or transfer ownership."

    # Project
    PROJECT_NOT_MEMBER = "This user is not a member of the project."

    # Task
    TASK_ALREADY_ASSIGNED = "Task is already assigned to a user."
    TASK_NOT_FOUND = "Task not found."
    INVALID_STATUS = "Invalid status value."
    INVALID_PRIORITY = "Invalid priority value."
    PERMISSION_DENIED = "You do not have permission."

    TASK_CANNOT_REVERT = "You cannot revert a task from DONE status."
    TASK_NOT_OWNED = "You are not assigned to this task."
    TASK_NOT_ALLOWED = "You are not allowed to perform this action."
    # General
    PERMISSION_DENIED = "You do not have permission to perform this action."
    USER_NOT_IN_PROJECT = "This user is not part of the project."
    INVALID_OPERATION = "This operation is not allowed."

    #invitation
    WORKSPACE_NOT_FOUND = "Workspace not found."
    PROJECT_NOT_FOUND = "Project not found."

    EMAIL_REQUIRED = "Email and workspace_id are required."
    PROJECT_ID_REQUIRED = "project_id is required."

    INVITATION_ALREADY_ACCEPTED = "This user is already a member."
    INVITATION_NOT_FOUND = "Invitation not found."

    INVITATION_FORBIDDEN = "This invitation was not sent to your email address."
    INVITATION_REJECT_FORBIDDEN = "You do not have permission to reject this invitation."

    INVITATION_REJECTED_SUCCESS = "Invitation rejected successfully."
    INVITATION_ACCEPTED_SUCCESS = "You have successfully joined the workspace/project."

    INVITATION_SENT_SUCCESS = "Invitation sent successfully."
    INVITATION_RESENT_SUCCESS = "Invitation resent and updated."

    PROJECT_INVITATION_PROCESSED = "Project invitations and additions processed successfully."
    WORKSPACE_MEMBER_ALREADY_EXISTS = "User is already a member."

