from django.db import transaction
from django.shortcuts import get_object_or_404
from drf_spectacular.utils import extend_schema, extend_schema_view
from rest_framework import status, viewsets
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from users.errors.exceptions import (
    BaseAppException,
    OnlyOneWorkspaceAdminError,
    PermissionDeniedError,
    ProjectRoleNotFound,
    RoleRequiredError,
)
from users.errors.messages.success import success_response
from users.models import WorkSpace, WorkSpaceMember, ProjectRole, Task
from ..permissions import IsTeamManagerForProject, IsWorkspaceOwner
from ..serializers import ProjectMemberDetailSerializer, WorkSpaceMemberDetailSerializer


@extend_schema_view(
    list=extend_schema(tags=['الأعضاء'], summary="استعراض قائمة أعضاء المشروع"),
    retrieve=extend_schema(tags=['الأعضاء'], summary="تفاصيل عضو معين"),
    destroy=extend_schema(tags=['الأعضاء'], summary="حذف عضو من المشروع"),
    partial_update=extend_schema(tags=['الأدوار'], summary="تغيير دور الموظف داخل المشروع"),
)
class ProjectMemberViewSet(viewsets.ModelViewSet):
    permission_classes = [IsAuthenticated, IsTeamManagerForProject]
    serializer_class = ProjectMemberDetailSerializer

    def get_serializer_context(self):
        context = super().get_serializer_context()
        context['project_id'] = self.kwargs.get('project_pk')
        return context

    def get_queryset(self):
        project_id = self.kwargs.get('project_pk')
        return ProjectRole.objects.filter(project_id=project_id).select_related('user', 'project')

    def get_object(self):
        project_id = self.kwargs.get("project_pk")
        user_id = self.kwargs.get("pk")
        return get_object_or_404(ProjectRole, project_id=project_id, user_id=user_id)

    def list(self, request, *args, **kwargs):
        queryset = self.get_queryset()
        serializer = self.get_serializer(queryset, many=True)
        return Response(success_response(
            message="Project members retrieved successfully",
            code="PROJECT_MEMBERS_RETRIEVED",
            data=serializer.data,
        ), status=status.HTTP_200_OK)

    def retrieve(self, request, *args, **kwargs):
        member = self.get_object()
        serializer = self.get_serializer(member)
        return Response(success_response(
            message="Project member retrieved successfully",
            code="PROJECT_MEMBER_RETRIEVED",
            data=serializer.data,
        ), status=status.HTTP_200_OK)

    def partial_update(self, request, *args, **kwargs):
        project_id = kwargs.get('project_pk')
        member_id = kwargs.get('pk')

        if not ProjectRole.objects.filter(
            project_id=project_id,
            user=request.user,
            role__in=['MANAGER', 'ADMIN'],
        ).exists():
            raise PermissionDeniedError()

        member = ProjectRole.objects.filter(project_id=project_id, user_id=member_id).first()
        if not member:
            raise ProjectRoleNotFound()

        new_role = request.data.get('role')
        if not new_role:
            raise RoleRequiredError()

        if new_role not in ['ADMIN', 'MANAGER', 'EMPLOYEE']:
            raise BaseAppException(
                detail="Invalid project role",
                code="INVALID_PROJECT_ROLE",
                status_code=400,
            )

        if new_role == "ADMIN":
            existing_admin = ProjectRole.objects.filter(project_id=project_id, role="ADMIN").exclude(user_id=member_id)
            if existing_admin.exists():
                raise OnlyOneWorkspaceAdminError()

        member.role = new_role
        member.save(update_fields=['role'])

        return Response(success_response(
            message="Member role updated successfully",
            code="PROJECT_MEMBER_ROLE_UPDATED",
            data={
                "member_id": member.id,
                "user_id": member.user.id,
                "role": member.role,
            },
        ), status=status.HTTP_200_OK)

    def destroy(self, request, *args, **kwargs):
        project_id = kwargs.get('project_pk')
        member_id = kwargs.get('pk')

        if not ProjectRole.objects.filter(
            project_id=project_id,
            user=request.user,
            role__in=['MANAGER', 'ADMIN'],
        ).exists():
            raise PermissionDeniedError()

        member = self.get_object()
        if member.user_id == request.user.id:
            raise BaseAppException(
                detail="You cannot remove yourself from this endpoint. Use leave project instead.",
                code="CANNOT_REMOVE_SELF",
                status_code=400,
            )

        if member.role in ["ADMIN", "MANAGER"]:
            other_manager_exists = ProjectRole.objects.filter(
                project_id=project_id,
                role__in=["ADMIN", "MANAGER"],
            ).exclude(user_id=member_id).exists()
            if not other_manager_exists:
                raise OnlyOneWorkspaceAdminError()

        with transaction.atomic():
            Task.objects.filter(project_id=project_id, assigned_to_id=member_id).update(
                assigned_to=None,
                status="UNASSIGNED",
            )
            member.delete()

        return Response(success_response(
            message="Project member removed successfully",
            code="PROJECT_MEMBER_REMOVED",
            data={"user_id": int(member_id), "project_id": int(project_id)},
        ), status=status.HTTP_200_OK)


@extend_schema_view(
    list=extend_schema(tags=['الأعضاء'], summary="استعراض قائمة أعضاء مساحة العمل"),
    retrieve=extend_schema(tags=['الأعضاء'], summary="عرض تفاصيل عضو"),
    destroy=extend_schema(tags=['الأعضاء'], summary="إزالة عضو من مساحة العمل"),
)
class WorkSpaceMemberViewSet(viewsets.ModelViewSet):
    permission_classes = [IsAuthenticated, IsWorkspaceOwner]
    serializer_class = WorkSpaceMemberDetailSerializer

    def get_serializer_context(self):
        context = super().get_serializer_context()
        context['workspace_id'] = self.kwargs.get('workspace_pk')
        return context

    def get_queryset(self):
        workspace_id = self.kwargs.get('workspace_pk')
        return WorkSpaceMember.objects.filter(workspace_id=workspace_id).select_related('user', 'workspace')

    def get_object(self):
        workspace_id = self.kwargs.get('workspace_pk')
        user_id = self.kwargs.get('pk')
        return get_object_or_404(WorkSpaceMember, workspace_id=workspace_id, user_id=user_id)

    def _can_manage_workspace(self, request, workspace_id):
        return WorkSpace.objects.filter(id=workspace_id, creator=request.user).exists() or WorkSpaceMember.objects.filter(
            workspace_id=workspace_id,
            user=request.user,
            role='ADMIN',
        ).exists()

    def list(self, request, *args, **kwargs):
        workspace_id = kwargs.get('workspace_pk')
        if not self._can_manage_workspace(request, workspace_id):
            raise PermissionDeniedError()
        queryset = self.get_queryset()
        serializer = self.get_serializer(queryset, many=True)
        return Response(success_response(
            message="Workspace members retrieved successfully",
            code="WORKSPACE_MEMBERS_RETRIEVED",
            data=serializer.data,
        ), status=status.HTTP_200_OK)

    def retrieve(self, request, *args, **kwargs):
        workspace_id = kwargs.get('workspace_pk')
        if not self._can_manage_workspace(request, workspace_id):
            raise PermissionDeniedError()
        member = self.get_object()
        serializer = self.get_serializer(member)
        return Response(success_response(
            message="Workspace member retrieved successfully",
            code="WORKSPACE_MEMBER_RETRIEVED",
            data=serializer.data,
        ), status=status.HTTP_200_OK)

    def partial_update(self, request, *args, **kwargs):
        workspace_id = kwargs.get('workspace_pk')
        user_id = kwargs.get('pk')

        if not self._can_manage_workspace(request, workspace_id):
            raise PermissionDeniedError()

        member = self.get_object()
        new_role = request.data.get('role')

        if new_role not in ['ADMIN', 'MEMBER']:
            raise BaseAppException(
                detail="Invalid workspace role",
                code="INVALID_WORKSPACE_ROLE",
                status_code=400,
            )

        if new_role == "ADMIN":
            existing_admin = WorkSpaceMember.objects.filter(workspace_id=workspace_id, role="ADMIN").exclude(user_id=user_id)
            if existing_admin.exists():
                raise OnlyOneWorkspaceAdminError()

        member.role = new_role
        member.save(update_fields=['role'])

        return Response(success_response(
            message="Workspace member role updated successfully",
            code="WORKSPACE_MEMBER_ROLE_UPDATED",
            data={"user_id": int(user_id), "workspace_id": int(workspace_id), "role": member.role},
        ), status=status.HTTP_200_OK)

    def destroy(self, request, *args, **kwargs):
        workspace_id = kwargs.get('workspace_pk')
        user_id = kwargs.get('pk')

        if not self._can_manage_workspace(request, workspace_id):
            raise PermissionDeniedError()

        workspace = get_object_or_404(WorkSpace, id=workspace_id)
        if workspace.creator_id == int(user_id):
            raise BaseAppException(
                detail="لا يمكن حذف مالك مساحة العمل. يجب نقل الملكية أولاً.",
                code="WORKSPACE_OWNER_CANNOT_BE_REMOVED",
                status_code=400,
            )

        with transaction.atomic():
            ProjectRole.objects.filter(project__workspace_id=workspace_id, user_id=user_id).delete()
            Task.objects.filter(project__workspace_id=workspace_id, assigned_to_id=user_id).update(
                assigned_to=None,
                status="UNASSIGNED",
            )
            WorkSpaceMember.objects.filter(workspace_id=workspace_id, user_id=user_id).delete()

        return Response(success_response(
            message="Workspace member removed successfully",
            code="WORKSPACE_MEMBER_REMOVED",
            data={"user_id": int(user_id), "workspace_id": int(workspace_id)},
        ), status=status.HTTP_200_OK)
