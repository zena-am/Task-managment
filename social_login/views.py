from django.shortcuts import render
from rest_framework.decorators import action
from django.shortcuts import render, redirect
from django.contrib.auth.decorators import login_required
from django.contrib.auth  import get_user_model
from django.conf import settings
from django.contrib.auth import authenticate, logout
from django.contrib import messages
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework_simplejwt.tokens import RefreshToken
from google.oauth2 import id_token
from google.auth.transport import requests
from users.models import User
from firebase_admin import auth as firebase_auth
from drf_spectacular.utils import extend_schema, OpenApiExample, OpenApiResponse
from .serializers import GoogleAuthSerializer
"""
class Token(TokenObtainPairView):
    serializer_class = MyTokenObtainPairSerializer

"""


class GoogleTokenAuthView(APIView):
    def post(self, request):
        token = request.data.get('google_token')
        try:
            idinfo = id_token.verify_oauth2_token(token, requests.Request(), "YOUR_GOOGLE_CLIENT_ID")

            user, created = User.objects.get_or_create(email=idinfo['email'], defaults={'username': idinfo['name']})

            refresh = RefreshToken.for_user(user)
            return Response({
                'access': str(refresh.access_token),
                'refresh': str(refresh),
                'username': user.username
            })
        except ValueError:
            return Response({'error': 'Invalid Token'}, status=400)
###########################################################################
@extend_schema(
        summary="تسجيل الدخول عبر جوجل ",
        description="يستقبل هذا الرابط التوكن القادم من فايربيز، يتحقق منه، وينشئ حساباً للمستخدم إذا لم يكن موجوداً، ثم يعيد توكنات الدخول الخاصة بالنظام ",
        responses=GoogleAuthSerializer,
    )
@action(detail=False, methods=['get'], url_path='googleLogin')
class GoogleFirebaseAuthView(APIView):
    def post(self, request):

        id_token = request.data.get('firebase_token')

        try:

            decoded_token = firebase_auth.verify_id_token(id_token)
            email = decoded_token.get('email')
            name = decoded_token.get('name', email.split('@')[0])


            user, created = User.objects.get_or_create(
                email=email,

                defaults={'username': email, 'first_name': name}
            )

            refresh = RefreshToken.for_user(user)
            return Response({
                'access': str(refresh.access_token),
                'refresh': str(refresh),
                'username': user.username
            })

        except Exception as e:
            return Response({'error': 'Invalid Firebase Token'}, status=400)
##############################################################################################33
CustomUser = get_user_model()
from rest_framework_simplejwt.tokens import RefreshToken
from django.http import JsonResponse
from django.contrib.auth.decorators import login_required
def login_view(request):
    return render(request, 'login.html')


@login_required
def success_page_view(request):

    user = request.user

    refresh = RefreshToken.for_user(user)
    access_token = str(refresh.access_token)
    refresh_token = str(refresh)
    return render(request, 'success.html', {
        'access': access_token,
        'refresh': refresh_token,
        'username': user.username
    })

@login_required
def home_view(request):

    if request.headers.get('Accept') == 'application/json':
        return JsonResponse({
            "message": "Logged in successfully",
            "email": request.user.email,
        })

    return redirect('profile')

""""
@login_required
def home_view(request):
    return render(request, 'home.html')
    """


@login_required
def profile_view(request):

    return render(request, 'profile.html')


@login_required
def logout_page(request):
    logout(request)
    messages.success(request, 'You have been logged out successfully.')
    return redirect('/')


def signup_view(request):
    if request.method == 'POST':
        email = request.POST.get('email')
        password1 = request.POST.get('password1')
        password2 = request.POST.get('password2')


        if password1 != password2:
            messages.error(request, 'Passwords do not match. Please try again.')
            return render(request, 'signup.html')


        if CustomUser.objects.filter(email=email).exists():
            messages.error(request, 'Email is already in use. Please try another.')
            return render(request, 'signup.html')


        user = CustomUser.objects.create_user(username=email, email=email, password=password1)
        user.save()
        messages.success(request, 'Signup successful! You can now log in.')
        return redirect('login')

    return render(request, 'signup.html')


