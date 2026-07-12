from django.db.models import Q
from drf_spectacular.utils import extend_schema
from rest_framework import permissions, status, viewsets
from rest_framework.decorators import action
from rest_framework.response import Response

from users.errors.messages.success import success_response
from users.models import User
from ..serializers import UserSerializer


@extend_schema(tags=['البحث عن المستخدمين'])
class searchUserViewSet(viewsets.ReadOnlyModelViewSet):
    queryset = User.objects.filter(is_active=True)
    serializer_class = UserSerializer
    permission_classes = [permissions.IsAuthenticated]

    @extend_schema(
        summary="البحث عن المستخدمين",
        description="يسمح بالبحث باستخدام اسم المستخدم، البريد، الاسم الأول، أو الأخير.",
        responses={200: UserSerializer(many=True)},
    )
    @action(detail=False, methods=['get'])
    def search(self, request):
        query = request.query_params.get('q', '')
        if len(query) < 2:
            return Response(success_response(
                message="Search query must be at least 2 characters",
                code="SEARCH_QUERY_TOO_SHORT",
                data=[],
            ), status=status.HTTP_200_OK)

        users = User.objects.filter(
            is_active=True,
        ).filter(
            Q(username__icontains=query) |
            Q(email__icontains=query) |
            Q(first_name__icontains=query) |
            Q(last_name__icontains=query)
        ).exclude(id=request.user.id)[:10]
        serializer = UserSerializer(users, many=True, context={'request': request})
        return Response(success_response(
            message="Users retrieved successfully",
            code="USERS_RETRIEVED",
            data=serializer.data,
        ), status=status.HTTP_200_OK)

    @extend_schema(summary="جلب بيانات مستخدم محدد بواسطة المعرف")
    def retrieve(self, request, *args, **kwargs):
        user = self.get_object()
        serializer = self.get_serializer(user)
        return Response(success_response(
            message="User retrieved successfully",
            code="USER_RETRIEVED",
            data=serializer.data,
        ), status=status.HTTP_200_OK)

    @extend_schema(summary="جلب قائمة بجميع المستخدمين")
    def list(self, request, *args, **kwargs):
        queryset = self.filter_queryset(self.get_queryset())
        serializer = self.get_serializer(queryset, many=True)
        return Response(success_response(
            message="Users retrieved successfully",
            code="USERS_RETRIEVED",
            data=serializer.data,
        ), status=status.HTTP_200_OK)
