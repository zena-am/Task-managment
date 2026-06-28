from django.urls import path
from social_login.views.firebase_auth_views import GoogleFirebaseAuthView
from social_login.views.setPassword import SetPasswordAPIView
from social_login.views.web import LoginAPIView
from social_login.views.web_auth_views import GoogleTokenAuthView
from rest_framework_simplejwt.views import TokenObtainPairView, TokenRefreshView
from django.urls import include, path
from  social_login import views

urlpatterns = [
    #هذا ل flutter مع للفاير بيز
    path('api/auth/google/', GoogleFirebaseAuthView.as_view(), name='google-auth'),

    path('api/token/', TokenObtainPairView.as_view(), name='token_obtain_pair'),
    path('api/token/refresh/', TokenRefreshView.as_view(), name='token_refresh'),
    path('api/google-login/', GoogleTokenAuthView.as_view(), name='google_login_api'),
    path("",views.home_view,name='home'),
    path("logout/",views.logout_page,name='logout'),
    path('profile/', views.profile_view, name='profile'),
    path("signup/",views.signup_view,name='signup'),
    path('auth/google/success/', views.success_page_view,name='google_login_success'),



    path('api/login/', LoginAPIView.as_view(), name='login-api'),
    path('api/set-password/', SetPasswordAPIView.as_view(), name='set-password-api'),
    #path("login/",views.login_page,name='login'),
    #path('success/', views.success_page_view, name='google_login_success'),
    ####### path('auth/google/success/', views.google_auth_receiver),

]