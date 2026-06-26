from rest_framework import status, viewsets
from rest_framework import viewsets
from rest_framework.permissions import IsAuthenticated
from django.shortcuts import get_object_or_404
from users.errors.exceptions import OnlyOneWorkspaceAdminError, PermissionDeniedError, ProjectRoleNotFound, RoleRequiredError
from users.errors.messages.success import success_response
from ..models import WorkSpaceMember
from ..serializers import WorkSpaceMemberDetailSerializer
from users import permissions
from ..serializers import ProjectMemberDetailSerializer
from ..models import ProjectRole, TechnicalReportForm, User
from drf_spectacular.utils import extend_schema, extend_schema_view
from rest_framework import viewsets
from ..permissions import  IsTeamManagerForProject, IsWorkspaceOwner, IsWorkspaceOwnerOrReadOnly
from rest_framework.response import Response
from django.db import transaction
from rest_framework import status
from users.models import WorkSpace, WorkSpaceMember, ProjectRole, Task

@extend_schema_view(
    list=extend_schema( tags=['الأعضاء'],summary="استعراض قائمة أعضاء المشروع", description="إرجاع قائمة بجميع المستخدمين المشاركين في مشروع معين"),
    retrieve=extend_schema( tags=['الأعضاء'],summary="تفاصيل عضو معين"),
    destroy=extend_schema( tags=['الأعضاء'],summary="حذف عضو من المشروع"),
    partial_update=extend_schema( tags=['الأدوار'],summary="تغيير دور الموظف داخل المشروع",description="تغيير دور"),
)
class ProjectMemberViewSet(viewsets.ModelViewSet):
    permission_classes = [IsAuthenticated,IsTeamManagerForProject]
    serializer_class = ProjectMemberDetailSerializer

    def get_queryset(self):
        project_id = self.kwargs.get('project_pk')
        return ProjectRole.objects.filter(project_id=project_id).select_related('user')

    def get_object(self):
        project_id = self.kwargs.get("project_pk")
        user_id = self.kwargs.get("pk")

        return get_object_or_404(
            ProjectRole,
            project_id=project_id,
            user_id=user_id
        )
    def get_queryset(self):
        print(self.kwargs)

        project_id = self.kwargs.get('project_pk')

        return ProjectRole.objects.filter(
            project_id=project_id
        ).select_related('user')

    from rest_framework import status
    from rest_framework.response import Response
    def partial_update(self, request, *args, **kwargs):
        project_id = kwargs.get('project_pk')
        member_id = kwargs.get('pk')

        if not ProjectRole.objects.filter(
            project_id=project_id,
            user=request.user,
            role__in=['MANAGER', 'ADMIN']
        ).exists():
            raise PermissionDeniedError()

        member = ProjectRole.objects.filter(
            project_id=project_id,
            user_id=member_id
        ).first()

        if not member:
            raise ProjectRoleNotFound()

        new_role = request.data.get('role')

        if not new_role:
            raise RoleRequiredError()

        if new_role == "ADMIN":
            existing_admin = ProjectRole.objects.filter(
                project_id=project_id,
                role="ADMIN"
            ).exclude(user_id=member_id)

            if existing_admin.exists():
                raise OnlyOneWorkspaceAdminError()

        member.role = new_role
        member.save(update_fields=['role'])

        return Response(
            success_response(
                message="Member role updated successfully",
                code="PROJECT_MEMBER_ROLE_UPDATED",
                data={
                    "member_id": member.id,
                    "user_id": member.user.id,
                    "role": member.role
                }
            ),
            status=status.HTTP_200_OK
        )
    from django.db import transaction

    def destroy(self, request, *args, **kwargs):
        project_id = kwargs.get('project_pk')
        member_id = kwargs.get('pk')

        if not ProjectRole.objects.filter(
            project_id=project_id,
            user=request.user,
            role__in=['MANAGER', 'ADMIN']
        ).exists():
            raise PermissionDeniedError()

        member = self.get_object()

        if member.role == "ADMIN":
            other_admin_exists = ProjectRole.objects.filter(
                project_id=project_id,
                role="ADMIN"
            ).exclude(user_id=member_id).exists()

            if not other_admin_exists:
                raise OnlyOneWorkspaceAdminError()

        with transaction.atomic():
            Task.objects.filter(
                project_id=project_id,
                assigned_to_id=member_id
            ).update(assigned_to=None)

            member.delete()

        return Response(status=status.HTTP_204_NO_CONTENT)

















@extend_schema_view(

    list=extend_schema(
        tags=['الأعضاء'],
        summary="استعراض قائمة أعضاء مساحة العمل",
        description="جلب قائمة بجميع المستخدمين المنضمين إلى مساحة عمل محددة عبر workspace_pk"
    ),
    retrieve=extend_schema(
        tags=['الأعضاء'],
        summary="عرض تفاصيل عضو",
        description="عرض البيانات الشخصية وإحصائيات المهام لعضو محدد في مساحة العمل"
    ),

    destroy=extend_schema(
        tags=['الأعضاء'],
        summary="إزالة عضو من مساحة العمل",
        description="حذف العضو من مساحة العمل نهائياً"
    ),
)
class WorkSpaceMemberViewSet(viewsets.ModelViewSet):
    permission_classes = [IsAuthenticated, IsWorkspaceOwner]
    serializer_class = WorkSpaceMemberDetailSerializer



    def get_queryset(self):
        workspace_id = self.kwargs.get('workspace_pk')

        return WorkSpaceMember.objects.filter(
            workspace_id=workspace_id
        ).select_related('user')

    def partial_update(self, request, *args, **kwargs):
        workspace_id = kwargs.get('workspace_pk')
        user_id = kwargs.get('pk')

        if not WorkSpaceMember.objects.filter(
            workspace_id=workspace_id,
            user=request.user,
            role__in=['ADMIN', 'MANAGER']
        ).exists():
            return Response({"detail": "ليس لديك صلاحية لتغيير الأدوار"}, status=403)

        member = WorkSpaceMember.objects.get(
            workspace_id=workspace_id,
            user_id=user_id
        )

        new_role = request.data.get('role')

        if new_role:
            member.role = new_role
            member.save()
            return Response({"detail": "تم تحديث الدور بنجاح"})

        return Response({"detail": "يرجى تحديد الدور الجديد"}, status=400)





    def destroy(self, request, *args, **kwargs):
        workspace_id = kwargs.get('workspace_pk')
        user_id = kwargs.get('pk')

        if not self._can_manage_workspace(request, workspace_id):
            raise PermissionDeniedError()

        workspace = get_object_or_404(WorkSpace, id=workspace_id)

        if workspace.creator_id == int(user_id):
            return Response(
                {"detail": "لا يمكن حذف مالك مساحة العمل. يجب نقل الملكية أولاً."},
                status=status.HTTP_400_BAD_REQUEST
            )

        with transaction.atomic():
            ProjectRole.objects.filter(
                project__workspace_id=workspace_id,
                user_id=user_id
            ).delete()

            Task.objects.filter(
                project__workspace_id=workspace_id,
                assigned_to_id=user_id
            ).update(assigned_to=None)

            WorkSpaceMember.objects.filter(
                workspace_id=workspace_id,
                user_id=user_id
            ).delete()

        return Response(status=status.HTTP_204_NO_CONTENT)