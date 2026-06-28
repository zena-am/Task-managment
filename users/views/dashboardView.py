from django.db.models import Q
from django.shortcuts import get_object_or_404
from drf_spectacular.utils import extend_schema
from rest_framework import status
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from users.errors.messages.success import success_response
from ..models import WorkSpace
from ..serializers import DashboardSerializer


class DashboardView(APIView):
    permission_classes = [IsAuthenticated]

    @extend_schema(
        tags=['الواجهة الرئيسية'],
        summary="جلب بيانات الواجهة الرئيسية",
        description="يعيد كل ما تحتاجه واجهة التطبيق الرئيسية دفعة واحدة.",
        responses={200: DashboardSerializer},
    )
    def get(self, request):
        user = request.user
        workspace_id = request.query_params.get('workspace_id')
        workspace = None

        if workspace_id:
            workspace_qs = WorkSpace.objects.filter(
                Q(members=user) |
                Q(projects__projectrole__user=user, projects__projectrole__role__in=['ADMIN', 'MANAGER'])
            ).distinct()
            workspace = get_object_or_404(workspace_qs, id=workspace_id)

        dashboard_data = {
            "user_name": f"{user.first_name} {user.last_name}".strip() or user.username,
            "user_avatar": user.avatar.url if getattr(user, 'avatar', None) else None,
            "user": user,
            "workspace": workspace,
        }

        serializer = DashboardSerializer(dashboard_data, context={'request': request})
        return Response(success_response(
            message="Dashboard retrieved successfully",
            code="DASHBOARD_RETRIEVED",
            data=serializer.data,
        ), status=status.HTTP_200_OK)
