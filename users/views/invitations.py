from django.db.models import Q
from django.shortcuts import get_object_or_404
from rest_framework import viewsets, mixins, status
from rest_framework.decorators import action
from rest_framework.pagination import PageNumberPagination
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from drf_spectacular.utils import extend_schema

from users.errors.exceptions import (
    BaseAppException,
    InvitationAlreadyAccepted,
    InvitationForbidden,
    InvitationRejectForbidden,
)
from users.errors.messages.success import success_response
from users.services.invitationsService import InvitationService
from ..models import Invitation, ProjectRole, WorkSpace, WorkSpaceMember
from ..serializers import InvitationSerializer


@extend_schema(tags=['دعوة أعضاء'])
class InvitationViewSet(
    mixins.RetrieveModelMixin,
    mixins.ListModelMixin,
    mixins.CreateModelMixin,
    viewsets.GenericViewSet,
):
    pagination_class = PageNumberPagination
    serializer_class = InvitationSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        user = self.request.user
        queryset = Invitation.objects.filter(
            Q(receiver_email=user.email) | Q(sender=user)
        ).select_related('sender', 'receiver', 'workspace', 'project')

        invitation_type = self.request.query_params.get('type')
        if invitation_type == 'sent':
            return queryset.filter(sender=user)
        if invitation_type == 'received':
            return queryset.filter(receiver_email=user.email)
        return queryset

    def get_object(self):
        queryset = self.get_queryset()
        return get_object_or_404(queryset, pk=self.kwargs['pk'])

    @extend_schema(
        summary="جلب قائمة الدعوات الخاصة بالمستخدم",
        description="يعيد الدعوات الواردة والصادرة للمستخدم الحالي. يمكن استخدام type=received أو type=sent.",
    )
    def list(self, request, *args, **kwargs):
        queryset = self.filter_queryset(self.get_queryset())
        page = self.paginate_queryset(queryset)
        if page is not None:
            serializer = self.get_serializer(page, many=True)
            paginated = self.paginator.get_paginated_response(serializer.data)
            return Response(success_response(
                message="Invitations retrieved successfully",
                code="INVITATIONS_RETRIEVED",
                data=paginated.data,
            ), status=status.HTTP_200_OK)

        serializer = self.get_serializer(queryset, many=True)
        return Response(success_response(
            message="Invitations retrieved successfully",
            code="INVITATIONS_RETRIEVED",
            data=serializer.data,
        ), status=status.HTTP_200_OK)

    @extend_schema(
        summary="جلب تفاصيل دعوة محددة",
        description="يعيد تفاصيل دعوة محددة إذا كان المستخدم الحالي هو المرسل أو المستقبل.",
    )
    def retrieve(self, request, *args, **kwargs):
        invitation = self.get_object()
        serializer = self.get_serializer(invitation)
        return Response(success_response(
            message="Invitation retrieved successfully",
            code="INVITATION_RETRIEVED",
            data=serializer.data,
        ), status=status.HTTP_200_OK)

    @extend_schema(
        summary="إرسال دعوة جديدة لمساحة عمل",
        description="يرسل دعوة واحدة أو عدة دعوات للانضمام لمساحة العمل.",
        responses={201: InvitationSerializer},
    )
    @action(detail=False, methods=['post'])
    def send_workspace_invitation(self, request):
        result = InvitationService.send_workspace_invitation(
            sender=request.user,
            data=request.data,
        )
        return Response(success_response(
            message="Workspace invitation processed successfully",
            code="WORKSPACE_INVITATION_PROCESSED",
            data=result,
        ), status=status.HTTP_201_CREATED)

    @extend_schema(
        summary="إرسال دعوة جديدة للمشروع",
        description="يرسل دعوة للمشروع أو يضيف أعضاء موجودين مباشرة حسب members_ids.",
        responses={201: InvitationSerializer},
    )
    @action(detail=False, methods=['post'])
    def send_project_invitation(self, request):
        result = InvitationService.send_project_invitation(
            sender=request.user,
            data=request.data,
        )
        return Response(success_response(
            message="Project invitation processed successfully",
            code="PROJECT_INVITATION_PROCESSED",
            data=result,
        ), status=status.HTTP_201_CREATED)

    @extend_schema(summary="إلغاء دعوة")
    @action(detail=True, methods=['delete'])
    def revoke(self, request, pk=None):
        invitation = self.get_object()

        if invitation.sender_id != request.user.id:
            raise BaseAppException(
                detail="You can only revoke your own invitations",
                code="INVITATION_REVOKE_FORBIDDEN",
                status_code=403,
            )

        if invitation.status == "ACCEPTED":
            raise InvitationAlreadyAccepted()

        invitation_id = invitation.id
        invitation.delete()

        return Response(success_response(
            message="Invitation revoked successfully",
            code="INVITATION_REVOKED",
            data={"invitation_id": invitation_id},
        ), status=status.HTTP_200_OK)

    @extend_schema(summary="قبول دعوة")
    @action(detail=True, methods=['post'])
    def accept(self, request, pk=None):
        invitation = self.get_object()
        if invitation.receiver_email != request.user.email:
            raise InvitationForbidden()

        result = InvitationService.accept_invitation(invitation, request.user)
        return Response(success_response(
            message="Invitation accepted successfully",
            code="INVITATION_ACCEPTED",
            data=result,
        ), status=status.HTTP_200_OK)

    @extend_schema(summary="رفض دعوة")
    @action(detail=True, methods=['post'])
    def reject(self, request, pk=None):
        invitation = self.get_object()
        if invitation.receiver_email != request.user.email:
            raise InvitationRejectForbidden()

        result = InvitationService.reject_invitation(invitation, request.user)
        return Response(success_response(
            message="Invitation rejected successfully",
            code="INVITATION_REJECTED",
            data=result,
        ), status=status.HTTP_200_OK)


@extend_schema(tags=['Invitation Management'])
class invitationsMembers(viewsets.ViewSet):
    pagination_class = PageNumberPagination
    permission_classes = [IsAuthenticated]

    @extend_schema(summary="دعوات أعضاء المشروع")
    @action(detail=False, methods=['get'], url_path='project/(?P<project_id>[^/.]+)')
    def list_project_invitations(self, request, project_id=None):
        status_param = request.query_params.get('status')
        valid_statuses = ['PENDING', 'ACCEPTED', 'REJECTED']
        if status_param and status_param not in valid_statuses:
            raise BaseAppException(detail="Invalid status", code="INVALID_STATUS", status_code=400)

        if not ProjectRole.objects.filter(
            project_id=project_id,
            user=request.user,
            role__in=['ADMIN', 'MANAGER'],
        ).exists():
            raise BaseAppException(detail="Permission denied", code="PERMISSION_DENIED", status_code=403)

        invitations = Invitation.objects.filter(project_id=project_id)
        if status_param:
            invitations = invitations.filter(status=status_param)

        serializer = InvitationSerializer(invitations, many=True, context={'request': request})
        return Response(success_response(
            message="Project invitations retrieved successfully",
            code="PROJECT_INVITATIONS_RETRIEVED",
            data=serializer.data,
        ))

    @extend_schema(summary="دعوات أعضاء الفضاء")
    @action(detail=False, methods=['get'], url_path='workspace/(?P<workspace_id>[^/.]+)')
    def list_workspace_invitations(self, request, workspace_id=None):
        status_param = request.query_params.get('status')
        valid_statuses = ['PENDING', 'ACCEPTED', 'REJECTED']
        if status_param and status_param not in valid_statuses:
            raise BaseAppException(detail="Invalid status", code="INVALID_STATUS", status_code=400)

        can_manage_workspace = WorkSpace.objects.filter(id=workspace_id, creator=request.user).exists() or WorkSpaceMember.objects.filter(
            workspace_id=workspace_id,
            user=request.user,
            role='ADMIN',
        ).exists()
        if not can_manage_workspace:
            raise BaseAppException(detail="Permission denied", code="PERMISSION_DENIED", status_code=403)

        invitations = Invitation.objects.filter(workspace_id=workspace_id, project__isnull=True)
        if status_param:
            invitations = invitations.filter(status=status_param)

        serializer = InvitationSerializer(invitations, many=True, context={'request': request})
        return Response(success_response(
            message="Workspace invitations retrieved successfully",
            code="WORKSPACE_INVITATIONS_RETRIEVED",
            data=serializer.data,
        ))
