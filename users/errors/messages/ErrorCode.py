class ErrorMessages:
    # =========================
    # General
    # =========================
    VALIDATION_ERROR = "Validation error."
    NOT_AUTHENTICATED = "Authentication required."
    SERVER_ERROR = "Internal server error."
    BUSINESS_ERROR = "Application error."
    PERMISSION_DENIED = "You do not have permission to perform this action."
    INVALID_OPERATION = "This operation is not allowed."

    # =========================
    # User
    # =========================
    PHONE_VALIDATION_ERROR = (
        "Please enter a valid phone number in international format "
        "(e.g., '+9665xxxxxxxx' or without '+'). Only 9 to 15 digits are allowed."
    )

    PROFILE_INCOMPLETE_ERROR = (
        "Please complete your profile details (avatar and phone) "
        "before creating or managing projects."
    )

    # =========================
    # Workspace
    # =========================
    INVALID_WORKSPACE_EMAIL = (
        "The email address is invalid. It must end with .com, .org, .net, or .edu"
    )

    WORKSPACE_ACCESS_DENIED = (
        "You cannot create or manage a project in a workspace you are not a member of."
    )

    WORKSPACE_CANNOT_LEAVE_AS_CREATOR = (
        "As the creator, you cannot leave this workspace. "
        "You must delete it or transfer ownership."
    )

    WORKSPACE_NOT_FOUND = "Workspace not found."
    WORKSPACE_MEMBER_ALREADY_EXISTS = "User is already a member."

    # =========================
    # Project
    # =========================
    PROJECT_NOT_MEMBER = "This user is not a member of the project."
    PROJECT_NOT_FOUND = "Project not found."
    USER_NOT_IN_PROJECT = "This user is not part of the project."

    # =========================
    # Task
    # =========================
    TASK_ALREADY_COMPLETED = "Task is already completed."
    TASK_ALREADY_ASSIGNED = "Task is already assigned to a user."
    TASK_NOT_FOUND = "Task not found."
    INVALID_STATUS = "Invalid status value."
    INVALID_PRIORITY = "Invalid priority value."
    TASK_CANNOT_REVERT = "You cannot revert a task from DONE status."
    TASK_NOT_OWNED = "You are not assigned to this task."
    TASK_NOT_ALLOWED = "You are not allowed to perform this action."
    TECHNICAL_REPORT_MISSING = "Cannot move to REVIEW: technical report is missing."

    # =========================
    # Invitation
    # =========================
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


    USER_NOT_FOUND = "User not found."
    INVITATION_FAILED = "Failed to process invitation."
    USER_ADDED_SUCCESS = "User added successfully."
    INVITATION_SENT_SUCCESS = "Invitation sent successfully."
    INVITATION_RESENT_SUCCESS="Invitation resent successfully."

    PROJECT_ALREADY_EXISTS = "A project with this name already exists in the workspace."