from django.db.models import Q
from drf_spectacular.utils import extend_schema
from rest_framework import permissions, status, viewsets
from rest_framework.decorators import action
from rest_framework.response import Response

from users.errors.messages.success import success_response
from users.models import User
from ..serializers import UserSerializer

"""
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
"""


from django.db.models import Q
from drf_spectacular.utils import extend_schema
from rest_framework import permissions, status, viewsets
from rest_framework.decorators import action
from rest_framework.response import Response

from users.errors.messages.success import success_response
from users.models import User
from users.serializers import UserSerializer


@extend_schema(tags=["البحث عن المستخدمين"])
class searchUserViewSet(viewsets.ReadOnlyModelViewSet):
    serializer_class = UserSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        return User.objects.filter(
            is_active=True,
            is_deleted=False,
        ).exclude(
            id=self.request.user.id,
        ).order_by(
            "username",
        )

    @extend_schema(
        summary="البحث عن المستخدمين",
        description=(
            "يسمح بالبحث عن المستخدمين الفعالين وغير المحذوفين "
            "باستخدام اسم المستخدم أو البريد الإلكتروني أو الاسم الأول أو الاسم الأخير."
        ),
        responses={200: UserSerializer(many=True)},
    )
    @action(
        detail=False,
        methods=["get"],
        url_path="search",
    )
    def search(self, request):
        query = request.query_params.get("q", "").strip()

        if len(query) < 2:
            return Response(
                success_response(
                    message="Search query must be at least 2 characters.",
                    code="SEARCH_QUERY_TOO_SHORT",
                    data=[],
                ),
                status=status.HTTP_200_OK,
            )

        users = self.get_queryset().filter(
            Q(username__icontains=query)
            | Q(email__icontains=query)
            | Q(first_name__icontains=query)
            | Q(last_name__icontains=query)
        )[:10]

        serializer = self.get_serializer(
            users,
            many=True,
            context={
                "request": request,
            },
        )

        return Response(
            success_response(
                message="Users retrieved successfully.",
                code="USERS_RETRIEVED",
                data=serializer.data,
            ),
            status=status.HTTP_200_OK,
        )

    @extend_schema(
        summary="جلب بيانات مستخدم محدد بواسطة المعرف",
        responses={200: UserSerializer},
    )
    def retrieve(self, request, *args, **kwargs):
        user = self.get_object()

        serializer = self.get_serializer(
            user,
            context={
                "request": request,
            },
        )

        return Response(
            success_response(
                message="User retrieved successfully.",
                code="USER_RETRIEVED",
                data=serializer.data,
            ),
            status=status.HTTP_200_OK,
        )

    @extend_schema(
        summary="جلب قائمة المستخدمين الفعالين",
        description=(
            "يعرض المستخدمين الفعالين وغير المحذوفين، "
            "مع استبعاد المستخدم الحالي."
        ),
        responses={200: UserSerializer(many=True)},
    )
    def list(self, request, *args, **kwargs):
        queryset = self.filter_queryset(
            self.get_queryset(),
        )

        page = self.paginate_queryset(queryset)

        if page is not None:
            serializer = self.get_serializer(
                page,
                many=True,
                context={
                    "request": request,
                },
            )

            paginated_response = self.get_paginated_response(
                serializer.data,
            )

            return Response(
                success_response(
                    message="Users retrieved successfully.",
                    code="USERS_RETRIEVED",
                    data=paginated_response.data,
                ),
                status=status.HTTP_200_OK,
            )

        serializer = self.get_serializer(
            queryset,
            many=True,
            context={
                "request": request,
            },
        )

        return Response(
            success_response(
                message="Users retrieved successfully.",
                code="USERS_RETRIEVED",
                data=serializer.data,
            ),
            status=status.HTTP_200_OK,
        )