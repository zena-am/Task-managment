from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from rest_framework import status
from drf_spectacular.utils import extend_schema
from ..serializers import DashboardSerializer
from ..models import WorkSpace
from django.shortcuts import get_object_or_404
from django.db.models import Q
class DashboardView(APIView):
    permission_classes = [IsAuthenticated]

    @extend_schema(
        tags=['الواجهة الرئيسية'],
        summary="جلب بيانات الواجهة الرئيسية ",
        description="يعيد هذا الرابط دفعة واحدة كل ما تحتاجه واجهة التطبيق الرئيسية (الهيدر، بطاقة التركيز، شريط الفضاءات، التنبيهات المخصصة حسب الرتبة، والنشاطات الأخيرة)",
        responses={200: DashboardSerializer}
    )

    def get(self, request):
        user = request.user
        workspace_id = request.query_params.get('workspace_id')
        workspace = None
        if workspace_id:
            workspace_qs = WorkSpace.objects.filter(
                Q(members=user) |
                Q(projects__projectrole__user=user, projects__projectrole__role='ADMIN')
            ).distinct()

            workspace = get_object_or_404(
                workspace_qs,
                id=workspace_id
            )

        dashboard_data = {
            "user_name": f"{user.first_name} {user.last_name}".strip() or user.username,
            "user_avatar": user.profile.avatar.url
            if hasattr(user, 'profile') and user.profile.avatar
            else None,
            "user": user,
            "workspace": workspace,
        }

        serializer = DashboardSerializer(
            dashboard_data,
            context={'request': request}
        )

        return Response(serializer.data, status=status.HTTP_200_OK)