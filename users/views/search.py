from rest_framework import viewsets, permissions
from rest_framework.decorators import action
from rest_framework.response import Response
from django.db.models import Q
from django.contrib.auth import get_user_model
from drf_spectacular.utils import extend_schema

from users.models import User
from ..serializers import UserSerializer



@extend_schema(tags=['البحث عن المستخدمين'])
class searchUserViewSet(viewsets.ReadOnlyModelViewSet):
    queryset = User.objects.all()
    serializer_class = UserSerializer
    permission_classes = [permissions.IsAuthenticated]
    @extend_schema(
        summary="البحث  عن المستخدمين",
        description="يسمح بالبحث عن المستخدمين باستخدام (اسم المستخدم، البريد الإلكتروني، الاسم الأول، أو الأخير). "
                    "يجب أن يتكون نص البحث من 3 أحرف على الأقل. يتم استثناء المستخدم الحالي من النتائج.",

        responses={200: UserSerializer(many=True)}
    )
    @action(detail=False, methods=['get'])
    def search(self, request):
        query = request.query_params.get('q', '')
        if len(query) < 3:
            return Response([])
        users = User.objects.select_related('profile').filter(
        Q(username__icontains=query) |
        Q(email__icontains=query) |
        Q(first_name__icontains=query) |
        Q(last_name__icontains=query)).exclude(id=request.user.id)[:10]
        serializer = UserSerializer(users, many=True)
        return Response(serializer.data)
    @extend_schema(summary="جلب بيانات مستخدم محدد بواسطة المعرف (ID)")
    def retrieve(self, request, *args, **kwargs):
        return super().retrieve(request, *args, **kwargs)
    @extend_schema(summary="جلب قائمة بجميع المستخدمين")
    def list(self, request, *args, **kwargs):
        return super().list(request, *args, **kwargs)