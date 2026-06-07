from rest_framework import viewsets
from rest_framework import viewsets
from rest_framework.permissions import IsAuthenticated
from ..models import WorkSpaceMember
from ..serializers import WorkSpaceMemberDetailSerializer
from users import permissions
from ..serializers import ProjectMemberDetailSerializer
from ..models import ProjectRole, TechnicalReportForm, User
from drf_spectacular.utils import extend_schema, extend_schema_view
from rest_framework import viewsets
from ..permissions import  IsTeamManagerForProject, IsWorkspaceOwnerOrReadOnly
from rest_framework.response import Response

@extend_schema_view(
    list=extend_schema( tags=['الأعضاء'],summary="استعراض قائمة أعضاء المشروع", description="إرجاع قائمة بجميع المستخدمين المشاركين في مشروع معين"),
    retrieve=extend_schema( tags=['الأعضاء'],summary="تفاصيل عضو معين"),
    destroy=extend_schema( tags=['الأعضاء'],summary="حذف عضو من المشروع"),
    partial_update=extend_schema(summary="تغيير دور الموظف داخل المشروع",description="تغيير دور"),
)
class ProjectMemberViewSet(viewsets.ModelViewSet):
    permission_classes = [IsAuthenticated, IsTeamManagerForProject]
    serializer_class = ProjectMemberDetailSerializer


    def get_queryset(self):
        project_id = self.kwargs.get('project_pk')
        return User.objects.filter(projectrole__project_id=project_id)

    def get_serializer_context(self):
        context = super().get_serializer_context()
        context['project_id'] = self.kwargs.get('project_pk')
        return context
    def partial_update(self, request, *args, **kwargs):
        if not ProjectRole.objects.filter(
            project_id=kwargs.get('project_pk'),
            user=request.user,
            role__in=['MANAGER', 'ADMIN']
        ).exists():
            return Response({"detail": "ليس لديك صلاحية لتغيير الأدوار"}, status=403)

        project_role = ProjectRole.objects.get(
            project_id=kwargs.get('project_pk'),
            user_id=kwargs.get('pk')
        )
        new_role = request.data.get('role')
        if new_role:
            project_role.role = new_role
            project_role.save()
            return Response({"detail": "تم تحديث الدور بنجاح"})

        return Response({"detail": "يرجى تحديد الدور الجديد"}, status=400)
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
    permission_classes = [IsAuthenticated,IsWorkspaceOwnerOrReadOnly]
    serializer_class = WorkSpaceMemberDetailSerializer

    def get_queryset(self):
        workspace_id = self.kwargs.get('workspace_pk')
        return User.objects.filter(workspacemember__workspace_id=workspace_id)

    def get_serializer_context(self):
        context = super().get_serializer_context()
        context['workspace_id'] = self.kwargs.get('workspace_pk')
        return context