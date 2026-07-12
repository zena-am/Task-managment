from users.errors.exceptions import BaseAppException


class UserAvailabilityService:
    """Central validation for operations that require a usable account."""

    @staticmethod
    def ensure_active(user, *, action="operation"):
        if user is None:
            raise BaseAppException(
                detail="User not found.",
                code="USER_NOT_FOUND",
                status_code=404,
            )

        if getattr(user, "is_deleted", False):
            raise BaseAppException(
                detail=f"A deleted user cannot be used for this {action}.",
                code="USER_DELETED",
                status_code=400,
            )

        if not user.is_active:
            raise BaseAppException(
                detail=f"An inactive user cannot be used for this {action}.",
                code="USER_INACTIVE",
                status_code=400,
            )

        return user
