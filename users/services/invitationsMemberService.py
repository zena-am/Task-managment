from django.db.models import Count

from users.models import Invitation


class InvitationMemberService:
    """Utility service for listing invitation statistics by owner."""

    @staticmethod
    def get_all_invitations(user, status=None, workspace_id=None, project_id=None):
        queryset = Invitation.objects.filter(sender=user)

        if workspace_id:
            queryset = queryset.filter(workspace_id=workspace_id)

        if project_id:
            queryset = queryset.filter(project_id=project_id)

        if status:
            queryset = queryset.filter(status=status)

        stats = queryset.values('status').annotate(count=Count('status'))
        return {
            "queryset": queryset.order_by('-created_at'),
            "stats": list(stats),
        }
