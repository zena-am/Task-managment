from drf_spectacular.utils import extend_schema, OpenApiParameter,OpenApiTypes
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework.permissions import AllowAny
from rest_framework_simplejwt.tokens import RefreshToken
from django.contrib.auth import authenticate

class LoginAPIView(APIView):
    permission_classes = [AllowAny]

    @extend_schema(
        tags=['الويب'],
        summary="تسجيل الدخول (جوجل أو كلمة مرور)",
        description="هذا المسار يستقبل توكن جوجل أو إيميل وكلمة مرور لتسجيل الدخول.",
        parameters=[
            OpenApiParameter(
                name='email',
                description='البريد الإلكتروني للمستخدم',
                required=False,
                type=OpenApiTypes.STR,
                location=OpenApiParameter.QUERY,
            ),
            OpenApiParameter(
                name='password',
                description='كلمة المرور الخاصة بالمستخدم',
                required=False,
                type=OpenApiTypes.STR,
                location=OpenApiParameter.QUERY,
            ),

        ], )
    def post(self, request):
        email = request.data.get('email')
        password = request.data.get('password')
        google_token = request.data.get('google_token')

        if email and password:
            user = authenticate(username=email, password=password)
            if user:
                refresh = RefreshToken.for_user(user)
                return Response({
                    "access": str(refresh.access_token),
                    "refresh": str(refresh),
                })
            return Response({"error": "الإيميل أو كلمة المرور غير صحيحة"}, status=401)

        elif google_token:

            return Response({"message": "تمت معالجة تسجيل الدخول عبر جوجل"})

        return Response({"error": "بيانات غير مكتملة"}, status=400)