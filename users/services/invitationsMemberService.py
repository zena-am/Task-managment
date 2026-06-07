from django.contrib.auth import get_user_model
from users.models import Invitation
from django.db.models import Count

class InvitationService:
    @staticmethod
    def get_all_invitations(user,status=None,workspace_id=None, project_id=None):
        stats = Invitation.objects.filter(sender=user).values('status').annotate(count=Count('status'))
        querySet = Invitation.objects.filter(sender=user)

        if workspace_id:
            querySet = querySet.filter(invitation__sender=user,workspace_id=workspace_id)

        if project_id:
            querySet = querySet.filter(invitation__sender=user,project_id=project_id)

        if status:
                query = query.filter(status=status)
        return{ querySet.order_by('-created_at'),
            stats
        }