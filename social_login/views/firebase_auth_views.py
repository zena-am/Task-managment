from firebase_admin import auth as firebase_auth
from drf_spectacular.utils import extend_schema
from ..serializers import GoogleAuthResponseSerializer
from rest_framework_simplejwt.tokens import RefreshToken
from rest_framework import status
from rest_framework.response import Response
from rest_framework.permissions import AllowAny
from django.views.decorators.csrf import csrf_exempt
from django.utils.decorators import method_decorator
from rest_framework.parsers import JSONParser
from ..firebase import firebase_auth
from rest_framework.views import APIView
from users.models import User



@method_decorator(csrf_exempt, name='dispatch')
class GoogleFirebaseAuthView(APIView):

    parser_classes = [JSONParser]
    permission_classes = [AllowAny]
    authentication_classes = []

    @extend_schema(
        summary="Google login via Firebase",
        description="Receives Firebase ID token from Flutter in Authorization header.",
        responses=GoogleAuthResponseSerializer,
    )
    def post(self, request):

        auth_header = request.headers.get("Authorization")

        if not auth_header:
            return Response(
                {"error": "Authorization header is required"},
                status=status.HTTP_400_BAD_REQUEST,
            )

        if not auth_header.startswith("Bearer "):
            return Response(
                {"error": "Invalid Authorization format"},
                status=status.HTTP_400_BAD_REQUEST,
            )

        firebase_token = auth_header.split("Bearer ")[1].strip()

        try:
            print("REQUEST ARRIVED")

            print(firebase_token[:100])

            print(len(firebase_token))

            print([len(x) for x in firebase_token.split('.')])
            decoded_token = firebase_auth.verify_id_token(firebase_token)

            print(decoded_token)

            email = decoded_token.get("email")

            if not email:
                return Response(
                    {"error": "Email not found"},
                    status=status.HTTP_400_BAD_REQUEST,
                )

            name = decoded_token.get("name") or email.split("@")[0]

            user, created = User.objects.get_or_create(
                email=email,
                defaults={
                    "username": email,
                    "first_name": name,
                },
            )

            if not user.first_name and name:
                user.first_name = name
                user.save(update_fields=["first_name"])

            refresh = RefreshToken.for_user(user)

            return Response(
                {
                    "access": str(refresh.access_token),
                    "refresh": str(refresh),
                    "username": user.username,
                    "email": user.email,
                },
                status=status.HTTP_200_OK,
            )

        except Exception as e:

            import traceback

            traceback.print_exc()

            return Response(
                {
                    "error": str(e),
                },
                status=500,
            )