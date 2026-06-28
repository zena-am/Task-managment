from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from drf_spectacular.utils import extend_schema, OpenApiExample

class SetPasswordAPIView(APIView):
    permission_classes = [IsAuthenticated]
    @extend_schema(
            tags=['تعيين كلمة المرور لتسجيل الدخول للأدمن داشبورد'],
        summary="تعيين كلمة مرور للحساب",
        description="هذا المسار يسمح للمستخدم (الذي سجل عبر جوجل) بتعيين كلمة مرور لحسابه ليتمكن من الدخول عبر البريد الإلكتروني لاحقاً. يتطلب إرسال الـ Access Token في الـ Header.",
        request={
            "application/json": {
                "type": "object",
                "properties": {
                    "password": {"type": "string", "format": "password", "description": "كلمة المرور الجديدة"},
                    "confirm_password": {"type": "string", "format": "password", "description": "تأكيد كلمة المرور"}
                },
                "required": ["password", "confirm_password"]
            }
        },
        responses={
            200: {"type": "object", "properties": {"message": {"type": "string"}}},
            400: {"type": "object", "properties": {"error": {"type": "string"}}}
        },
        examples=[
            OpenApiExample(
                'مثال طلب تعيين كلمة مرور',
                value={'password': 'MySecurePassword123', 'confirm_password': 'MySecurePassword123'},
            )
        ]
    )
    def post(self, request):
        password = request.data.get('password')
        confirm_password = request.data.get('confirm_password')

        if password != confirm_password:
            return Response({"error": "Passwords do not match"}, status=400)

        request.user.set_password(password)
        request.user.save()
        return Response({"message": "Password set successfully"})