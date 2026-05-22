from rest_framework import viewsets, permissions
from django.contrib.auth import get_user_model
from drf_spectacular.utils import extend_schema
from users.views.invitations import InvitationViewSet
from ..models import Project, ProjectRole, User, WorkSpaceMember, Invitation
from ..serializers import ProjectSerializer,ProjectCreateSerializer
from ..permissions import IsProjectManagerOrReadOnly
from ..utils import notify_existing_user, notify_new_user


class ProjectViewSet(viewsets.ModelViewSet):
    User = get_user_model()
    permission_classes = [permissions.IsAuthenticated, IsProjectManagerOrReadOnly]


    def get_serializer_class(self):

        if self.action in ['create', 'update', 'partial_update']:
            return ProjectCreateSerializer

        return ProjectSerializer

    def get_queryset(self):
        return Project.objects.filter(workspace__members=self.request.user).distinct()
#######################################################################

    def perform_create(self, serializer):
        project = serializer.save()
        ProjectRole.objects.get_or_create(project=project, user=self.request.user, defaults={'role': 'ADMIN'})

        if self.request.data.get('member_emails') or self.request.data.get('members_ids'):

            invitation_view = InvitationViewSet()
            invitation_view.request = self.request

            invitation_view.request.data['project_id'] = project.id
            invitation_view.request.data['workspace_id'] = project.workspace.id

            invitation_view.send_project_invitation(invitation_view.request)


























































"""
    def perform_create(self, serializer):
        project = serializer.save()
        ProjectRole.objects.get_or_create(project=project, user=self.request.user, defaults={'role': 'ADMIN'})

        InvitationViewSet.request.data['project_id'] = project.id
        InvitationViewSet.request.data['workspace_id'] = project.workspace.id

        InvitationViewSet.send_project_invitation(InvitationViewSet.request)

#################################
        member_emails = self.request.data.get('member_emails', [])
        if isinstance(member_emails, str):
            member_emails = [member_emails]
        if member_emails:
            self.handle_project_invitations(project, member_emails)
###############################
        members_ids = self.request.data.get('members_ids', [])

        if members_ids:
            for user_id in members_ids:
                try:
                    user_to_add = User.objects.get(id=user_id)
                    is_workspace_member = WorkSpaceMember.objects.filter(workspace=project.workspace,user=user_to_add ).exists()

                    if is_workspace_member:
                            WorkSpaceMember.objects.get_or_create(
                                workspace=project.workspace,
                                user=user_to_add,
                                defaults={'role': 'EMPLOYEE'}
                            )

                            ProjectRole.objects.get_or_create(
                                project=project,
                                user=user_to_add,
                                defaults={'role': 'DEV'}
                            )
                    else:

                        continue
                except User.DoesNotExist:
                    continue


#########################################
    def handle_project_invitations(self, project, emails):
        User = get_user_model()
        sender_name = self.request.user.get_full_name() or self.request.user.username
        workspace_name = project.workspace.name
        role = self.request.data.get('role', 'DEV')
        workspace = project.workspace

        for email in emails:
            existing_invitation = Invitation.objects.filter(receiver_email=email,workspace=project.workspace,project=project).first()
            if existing_invitation is not None:
                if existing_invitation.status == 'ACCEPTED':
                        continue
                if existing_invitation:
                    existing_invitation.status = 'PENDING'
                    existing_invitation.sender = self.request.user
                    existing_invitation.role = role
                    existing_invitation.save()
                    notify_existing_user(email, sender_name, workspace_name)
                    continue
            receiver = User.objects.filter(email=email).first()

            if receiver:

                Invitation.objects.create(
                    sender=self.request.user,
                    receiver=receiver,
                    receiver_email=email,
                    workspace=workspace,
                    project=project,
                    role=role,
                    status='PENDING'
                )

                notify_existing_user(email, sender_name, workspace_name)

            else:

                invitation = Invitation.objects.create(
                sender=self.request.user,
                receiver_email=email,
                project=project,
                workspace=project.workspace,
                role=role,
                status='PENDING')
                notify_new_user(email, sender_name, workspace_name)

"""