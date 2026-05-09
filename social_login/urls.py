from django.urls import path
from . import views
from rest_framework_simplejwt.views import TokenObtainPairView, TokenRefreshView
from django.urls import include, path
from  social_login import views
from .views import google_auth_receiver,GoogleTokenAuthView

urlpatterns = [
    path('api/token/', TokenObtainPairView.as_view(), name='token_obtain_pair'),
    path('api/token/refresh/', TokenRefreshView.as_view(), name='token_refresh'),
    path('auth/google/success/', views.google_auth_receiver),
    path('api/google-login/', GoogleTokenAuthView.as_view(), name='google_login_api'),
    path("",views.home_view,name='home'),
    #path("login/",views.login_page,name='login'),
    path("logout/",views.logout_page,name='logout'),
    path('profile/', views.profile_view, name='profile'),
    path("signup/",views.signup_view,name='signup'),

]