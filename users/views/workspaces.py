from django.shortcuts import get_object_or_404
from rest_framework import viewsets, permissions, status
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.views import APIView
from drf_spectacular.utils import extend_schema, extend_schema_view

from users.errors.exceptions import BaseAppException, PermissionDeniedError
from users.errors.messages.success import success_response
from users.services.WorkspaceService import WorkspaceServices
from ..models import User, WorkSpace, WorkSpaceMember
from ..serializers import WorkSpaceSerializer, WorkSpaceCreateSerializer
from ..permissions import IsWorkspaceOwnerOrReadOnly


@extend_schema_view(
    list=extend_schema(tags=['فضاءات العمل'], summary="عرض فضاءات العمل الخاصة بالمستخدم مرتبة حسب التثبيت"),
    create=extend_schema(tags=['فضاءات العمل'], summary="إنشاء فضاء عمل جديد"),
    retrieve=extend_schema(tags=['فضاءات العمل'], summary="جلب تفاصيل فضاء عمل محدد"),
    update=extend_schema(tags=['فضاءات العمل'], summary="(للمالك) تحديث كامل لفضاء العمل"),
    destroy=extend_schema(tags=['فضاءات العمل'], summary="(للمدير) حذف فضاء العمل"),
)
class WorkspaceViewSet(viewsets.ModelViewSet):
    permission_classes = [permissions.IsAuthenticated]

    def get_serializer_class(self):
        if self.action in ['create', 'update', 'partial_update']:
            return WorkSpaceCreateSerializer
        return WorkSpaceSerializer

    def get_queryset(self):
        return WorkspaceServices.get_user_workspaces(self.request.user)

    def create(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        result = WorkspaceServices.create_workspace(
            serializer=serializer,
            user=request.user,
            data=request.data,
        )
        response_serializer = WorkSpaceSerializer(
            result['workspace'],
            context=self.get_serializer_context(),
        )
        return Response(success_response(
            message="Workspace created successfully",
            code="WORKSPACE_CREATED",
            data={
                "workspace": response_serializer.data,
                "invitations_result": result.get("invitations_result"),
            },
        ), status=status.HTTP_201_CREATED)

    def update(self, request, *args, **kwargs):
        partial = kwargs.pop('partial', False)
        instance = self.get_object()
        serializer = self.get_serializer(instance, data=request.data, partial=partial)
        serializer.is_valid(raise_exception=True)
        result = WorkspaceServices.update_workspace(
            serializer=serializer,
            user=request.user,
            data=request.data,
        )
        response_serializer = WorkSpaceSerializer(
            result['workspace'],
            context=self.get_serializer_context(),
        )
        return Response(success_response(
            message="Workspace updated successfully",
            code="WORKSPACE_UPDATED",
            data={
                "workspace": response_serializer.data,
                "invitations_result": result.get("invitations_result"),
            },
        ), status=status.HTTP_200_OK)

    def partial_update(self, request, *args, **kwargs):
        kwargs['partial'] = True
        return self.update(request, *args, **kwargs)

    def destroy(self, request, *args, **kwargs):
        workspace = self.get_object()
        self.perform_destroy(workspace)
        return Response(success_response(
            message="Workspace deleted successfully",
            code="WORKSPACE_DELETED",
            data={"workspace_id": workspace.id},
        ), status=status.HTTP_200_OK)

    @extend_schema(tags=['الفضاءات'], summary="نقل ملكية")
    @action(detail=True, methods=['post'], url_path='transfer')
    def transfer_owner(self, request, pk=None):
        new_owner_id = request.data.get("new_owner_id")

        if not new_owner_id:
            raise BaseAppException(
                detail="new_owner_id is required",
                code="NEW_OWNER_REQUIRED",
                status_code=400,
            )

        try:
            new_owner_id = int(new_owner_id)
        except (TypeError, ValueError):
            raise BaseAppException(
                detail="new_owner_id must be a valid integer",
                code="INVALID_NEW_OWNER_ID",
                status_code=400,
            )

        workspace = self.get_object()
        new_owner = get_object_or_404(User, id=new_owner_id)

        if workspace.creator_id == new_owner_id:
            raise BaseAppException(
                detail="You are already the owner",
                code="ALREADY_OWNER",
                status_code=400,
            )

        if workspace.creator != request.user:
            raise PermissionDeniedError()

        if not WorkSpaceMember.objects.filter(workspace=workspace, user=new_owner).exists():
            raise BaseAppException(
                detail="User is not a member of this workspace",
                code="USER_NOT_IN_WORKSPACE",
                status_code=400,
            )

        result = WorkspaceServices.transfer_ownership(workspace, new_owner)

        return Response(success_response(
            message="Ownership transferred successfully",
            code="WORKSPACE_OWNERSHIP_TRANSFERRED",
            data=result,
        ), status=status.HTTP_200_OK)


class TogglePinWorkspaceAPIView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    @extend_schema(
        tags=['فضاءات العمل'],
        summary="(للموظف) تثبيت أو إلغاء تثبيت فضاء العمل",
    )
    def post(self, request, workspace_id):
        workspace = get_object_or_404(WorkSpace, id=workspace_id, members=request.user)
        result = WorkspaceServices.toggle_pin(user=request.user, workspace=workspace)

        return Response(success_response(
            message="Workspace pin updated successfully",
            code="WORKSPACE_PIN_UPDATED",
            data=result,
        ), status=status.HTTP_200_OK)


class LeaveWorkspaceAPIView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    @extend_schema(
        tags=['فضاءات العمل'],
        summary="(للموظف) مغادرة فضاء العمل",
    )
    def delete(self, request, workspace_id):
        workspace = get_object_or_404(WorkSpace, id=workspace_id, members=request.user)
        result = WorkspaceServices.leave_workspace(user=request.user, workspace=workspace)

        return Response(success_response(
            message="Left workspace successfully",
            code="WORKSPACE_LEFT",
            data=result,
        ), status=status.HTTP_200_OK)
