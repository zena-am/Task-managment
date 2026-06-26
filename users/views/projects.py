from rest_framework import viewsets, permissions
from drf_spectacular.utils import extend_schema
from users.models import Project
from rest_framework.response import Response
from rest_framework import status, viewsets
from django.db import transaction
from users.services.projectservice import ProjectService
from rest_framework.decorators import action
from rest_framework import status
from rest_framework.response import Response
from ..serializers import ProjectSerializer,ProjectCreateSerializer
from ..permissions import IsProjectManagerOrReadOnly
from drf_spectacular.utils import extend_schema, extend_schema_view
@extend_schema_view(
    list=extend_schema(
        tags=['المشاريع'],
        summary="جلب قائمة المشاريع",
        description="يعيد جميع المشاريع التي يملك المستخدم الحالي صلاحية الوصول إليها"
    ),
    retrieve=extend_schema(
        tags=['المشاريع'],
        summary="جلب تفاصيل مشروع",
        description="يعيد تفاصيل مشروع محدد مع بياناته الأساسية"
    ),
    create=extend_schema(
        tags=['المشاريع'],
        summary="إنشاء مشروع جديد",
        description="يقوم بإنشاء مشروع جديد داخل فضاء العمل المحدد"
    ),

    partial_update=extend_schema(
        tags=['المشاريع'],
        summary="تعديل جزئي لمشروع",
        description="تحديث بعض بيانات المشروع فقط"
    ),
    destroy=extend_schema(
        tags=['المشاريع'],
        summary="حذف مشروع",
        description="حذف مشروع من النظام"
    ),
)

class ProjectViewSet(viewsets.ModelViewSet):
    permission_classes = [permissions.IsAuthenticated, IsProjectManagerOrReadOnly]
    serializer_class = ProjectSerializer

    def get_serializer_class(self):
        if self.action in ['create', 'update', 'partial_update']:
            return ProjectCreateSerializer
        return ProjectSerializer



    def get_queryset(self):
        queryset = Project.objects.filter(
            workspace__members=self.request.user
        ).select_related(
            'workspace'
        ).distinct()

        workspace_id = self.request.query_params.get('workspace')

        if workspace_id:
            queryset = queryset.filter(workspace_id=workspace_id)

        return queryset

    @extend_schema(
    tags=['المشاريع'],
    summary="مغادرة المشروع",
    description="يسمح للمستخدم الحالي بمغادرة المشروع فقط دون مغادرة مساحة العمل")
    @action(detail=True, methods=['delete'], url_path='leave')
    def leave_project(self, request, pk=None):
        project = self.get_object()
        user = request.user

        member_role = ProjectRole.objects.filter(
            project=project,
            user=user
        ).first()

        if not member_role:
            return Response(
                {"detail": "أنت لست عضواً في هذا المشروع."},
                status=status.HTTP_400_BAD_REQUEST
            )

        if member_role.role in ['ADMIN', 'MANAGER']:
            has_other_manager = ProjectRole.objects.filter(
                project=project,
                role__in=['ADMIN', 'MANAGER']
            ).exclude(user=user).exists()

            if not has_other_manager:
                return Response(
                    {
                        "detail": "لا يمكنك مغادرة المشروع لأنك آخر مدير/أدمن. يجب تعيين مدير آخر أولاً."
                    },
                    status=status.HTTP_400_BAD_REQUEST
                )

        with transaction.atomic():
            Task.objects.filter(
                project=project,
                assigned_to=user
            ).update(
                assigned_to=None
            )

            member_role.delete()

        return Response(success_response(
    message="Left project successfully",
    code="PROJECT_LEFT",
    data={"project_id": project.id}
), status=status.HTTP_200_OK)



    def create(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        result = ProjectService.create(serializer,self.request)
        print(result.get("invitation_results"))
        response_data = {
            "project": serializer.data,
            "invitation_results": result.get("invitation_results")
        }

        return Response(success_response(
    message="Project created successfully",
    code="PROJECT_CREATED",
    data=response_data
), status=status.HTTP_201_CREATED)




    def destroy(self, request, *args, **kwargs):
        instance = self.get_object()
        self.perform_destroy(instance)
        return Response(success_response(
    message="Project deleted successfully",
    code="PROJECT_DELETED",
    data=None
), status=status.HTTP_200_OK)

#######################################################################
    """
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