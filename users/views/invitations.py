from rest_framework import viewsets, mixins, permissions, status
from rest_framework.decorators import APIView, action
from rest_framework.response import Response
from django.contrib.auth import get_user_model
from django.db import transaction
from drf_spectacular.utils import extend_schema
from users.errors.exceptions  import (BaseAppException, WorkspaceNotFound,  ProjectNotFound,  EmailAndWorkspaceRequired, ProjectIdRequired, InvitationAlreadyAccepted,InvitationForbidden,InvitationRejectForbidden,)
from users.errors.exceptions import ProjectNotFound
from users.errors.messages.ErrorCode import ErrorMessages
from users.errors.messages.success import success_response
from users.permissions import IsTeamManager, IsWorkspaceOwnerOrReadOnly
from rest_framework.permissions import IsAuthenticated
from users.serializers import task, user
from users.services.invitationsService import InvitationService
from ..models import Project
from ..models import Invitation, WorkSpaceMember, ProjectRole,WorkSpace
from ..serializers import InvitationSerializer
from ..utils import notify_existing_user, notify_new_user
from django.shortcuts import get_object_or_404
from rest_framework.pagination import PageNumberPagination

@extend_schema(tags=['دعوة أعضاء'])
class InvitationViewSet( mixins.RetrieveModelMixin, mixins.ListModelMixin, mixins.CreateModelMixin,viewsets.GenericViewSet ):
    pagination_class = PageNumberPagination
    queryset = Invitation.objects.all()
    serializer_class = InvitationSerializer
    permission_classes = [IsAuthenticated]
    @action(detail=True, methods=['delete'])
    def revoke(self, request, pk=None):
        invitation = self.get_object()

        if invitation.sender != request.user:
            raise ("You can only revoke your own invitations")

        if invitation.status == "ACCEPTED":
            raise BaseAppException(
                detail="Cannot revoke accepted invitation",
                code="INVITATION_ALREADY_ACCEPTED",
                status_code=400
            )

        invitation.delete()

        return Response(success_response(
            message="Invitation revoked successfully",
            code="INVITATION_REVOKED",
            data={"invitation_id": pk}
        ), status=status.HTTP_200_OK)
    def get_object(self):
        return get_object_or_404(
            Invitation,
            pk=self.kwargs["pk"],
            receiver_email=self.request.user.email
        )
    def get_queryset(self):
        return Invitation.objects.filter(receiver_email=self.request.user.email)

    @extend_schema(
        summary="جلب قائمة الدعوات الخاصة بالمستخدم",
        description="يعيد هذا الرابط قائمة بجميع الدعوات التي أُرسلت للمستخدم الحالي (بناءً على بريده الإلكتروني). تُستخدم هذه القائمة لعرض الطلبات المعلقة في واجهة التطبيق.",
    )
    def list(self, request, *args, **kwargs):
        return super().list(request, *args, **kwargs)


    @extend_schema(
        summary="جلب تفاصيل دعوة محددة",
        description="يستقبل معرف الدعوة (ID) ويعيد كافة التفاصيل المتعلقة بها، مثل اسم المرسل، مساحة العمل، المشروع، والدور المقترح.",
    )
    def retrieve(self, request, *args, **kwargs):
        return super().retrieve(request, *args, **kwargs)

########################################################################دعوات الفضاء
    @extend_schema(
        summary="إرسال دعوة جديدة",
        description="يقوم بإرسال دعوة للانضمام لمساحة عمل عبر البريد الإلكتروني. إذا كان المستخدم مسجلاً، يتم إخطاره، وإذا لم يكن، يتم إرسال دعوة خارجية له",
        responses={201: InvitationSerializer},
    )
    @action(detail=False, methods=['post'],permission_classes=[ IsAuthenticated,IsWorkspaceOwnerOrReadOnly ])
    def send_workspace_invitation(self, request):
        serializer = InvitationSerializer(data=request.data)
        if serializer.is_valid():
            result = InvitationService.send_workspace_invitation(
                request.user,
                serializer.validated_data
            )
            return Response(success_response(
                message="Invitation sent successfully",
                code="WORKSPACE_INVITATION_SENT",
                data=result
                ), status=status.HTTP_201_CREATED)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
########################################################################دعوات للمشروع
    @extend_schema(
        summary="  إرسال دعوة جديدة للمشروع",
        description="يقوم بإرسال دعوة للانضمام  للمشروع عبر البريد الإلكتروني. إذا كان المستخدم مسجلاً في الفضاء او موجود بالتطبيق بشكل عام، يتم إخطاره، وإذا لم يكن، يتم إرسال دعوة خارجية له",
        responses={201: InvitationSerializer},
    )
    @action(detail=False, methods=['post'])
    def send_project_invitation(self, request):
        result = InvitationService.send_project_invitation(
            sender=request.user,
            data=request.data
        )

        return Response(success_response(
            message="Project invitation processed successfully",
            code="PROJECT_INVITATION_PROCESSED",
            data=result
        ), status=status.HTTP_200_OK)

        User = get_user_model()
        member_emails = self.request.data.get('member_emails', [])
        if isinstance(member_emails, str):
            member_emails = [member_emails]

        project_id = request.data.get('project_id')
        role = request.data.get('role', 'MEMBER')

        try:
            project = Project.objects.get(id=project_id)
        except Project.DoesNotExist:
            raise ProjectNotFound()
        if not project_id:
                raise ProjectIdRequired()
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
                                defaults={'role':role}
                            )

                            ProjectRole.objects.get_or_create(
                                project=project,
                                user=user_to_add,
                                defaults={'role': role}
                            )
                    else:

                        WorkSpaceMember.objects.create(
                            workspace=project.workspace,
                            user=user_to_add,
                            role='EMPLOYEE'
                        )

                        ProjectRole.objects.get_or_create(
                            project=project,
                            user=user_to_add,
                            defaults={'role': role}
                        )
                except User.DoesNotExist:
                    continue
        User = get_user_model()
        sender_name = self.request.user.get_full_name() or self.request.user.username
        workspace_name = project.workspace.name
        role = self.request.data.get('role', 'DEV')
        workspace = project.workspace

        for email in member_emails:
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



        return Response({"detail": "Project invitations and additions processed successfully."}, status=status.HTTP_201_CREATED)










###################################################accept
    @extend_schema(
        summary="قبول دعوة",
        description="يسمح للمستخدم بقبول الدعوة الموجهة إليه. عند القبول، يتم إضافة المستخدم تلقائياً كعضو في مساحة العمل (وفي المشروع إن وجد) وتتغير حالة الدعوة إلى مقبول  ",
        responses={200: {"detail": "You have successfully joined..."}},
    )
    @action(detail=True, methods=['post'])
    def accept(self, request, pk=None):
        invitation = self.get_object()



        if invitation.receiver_email != request.user.email:
                    raise InvitationForbidden()

        with transaction.atomic():
            WorkSpaceMember.objects.get_or_create(
                workspace=invitation.workspace,
                user=request.user,
                defaults={'role': invitation.role}
            )


            if invitation.project:
                ProjectRole.objects.get_or_create(
                    project=invitation.project,
                    user=request.user,
                    defaults={'role': invitation.role}
                )

            invitation.status = 'ACCEPTED'
            invitation.save()

        return Response(success_response(
        message="Invitation accepted successfully",
        code="INVITATION_ACCEPTED",
        data={
            "workspace_id": invitation.workspace_id,
            "project_id": invitation.project_id
        }
), status=status.HTTP_200_OK)

###################################################reject
    @extend_schema(
        summary="رفض دعوة",
        description="يسمح للمستخدم برفض الدعوة الموجهة إليه، مما يؤدي لتغيير حالة الدعوة إلى  ومنعه من الانضمام عبر هذا الرابط.",
        responses={200: {"detail": "Invitation rejected successfully"}},
    )
    @action(detail=True, methods=['post'])
    def reject(self, request, pk=None):
        invitation = self.get_object()
        if invitation.receiver_email != request.user.email:
                raise InvitationRejectForbidden()
        invitation.status = 'REJECTED'
        invitation.receiver = request.user
        invitation.save()

        return Response(success_response(
    message="Invitation rejected successfully",
    code="INVITATION_REJECTED",
    data={"invitation_id": invitation.id}
), status=status.HTTP_200_OK)
###############################################################################################
@extend_schema(tags=['Invitation Management'])

class invitationsMembers(viewsets.ViewSet):
    pagination_class = PageNumberPagination
    permission_classes = [IsAuthenticated,IsTeamManager]


    @extend_schema(summary="دعوات أعضاء المشروع")
    @action(detail=False, methods=['get'], url_path='project/(?P<project_id>[^/.]+)')
    def list_project_invitations(self, request, project_id=None):
        status = request.query_params.get('status')
        valid_statuses = ['PENDING', 'ACCEPTED', 'REJECTED']
        if status and status not in valid_statuses:
            raise BaseAppException(
                detail="Invalid status",
                code="INVALID_STATUS",
                status_code=400
)
        invitations = InvitationService.get_all_invitations(user=request.user,project_id=project_id,status=status)
        serializer = InvitationSerializer(invitations, many=True)
        return Response(serializer.data)



    @extend_schema(summary="دعوات أعضاء الفضاء")
    @action(detail=False, methods=['get'], url_path='workspace/(?P<workspace_id>[^/.]+)')
    def list_workspace_invitations(self, request, workspace_id=None):
        status = request.query_params.get('status')
        valid_statuses = ['PENDING', 'ACCEPTED', 'REJECTED']
        if status and status not in valid_statuses:
            raise BaseAppException(
            detail="Invalid status",
            code="INVALID_STATUS",
            status_code=400
)
        invitations = InvitationService.get_all_invitations(workspace_id=workspace_id,user=request.user,status=status)

        serializer = InvitationSerializer(invitations, many=True)
        return Response(serializer.data)




