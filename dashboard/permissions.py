from rest_framework.permissions import BasePermission

from users.models import ProjectRole, WorkSpaceMember


class IsDashboardManager(BasePermission):
    """Allow workspace admins and project managers/admins to use manager APIs."""

    message = "You do not have permission to access the manager dashboard."

    def has_permission(self, request, view):
        user = request.user
        if not user or not user.is_authenticated:
            return False
        if user.is_superuser:
            return True
        return (
            WorkSpaceMember.objects.filter(user=user, role="ADMIN").exists()
            or ProjectRole.objects.filter(
                user=user,
                role__in=["ADMIN", "MANAGER"],
            ).exists()
        )
