#from rest_framework_simplejwt.views import TokenObtainPairView, TokenRefreshView
from django.urls import include, path
from users import views
from drf_spectacular.utils import extend_schema
from drf_spectacular.views import SpectacularAPIView, SpectacularSwaggerView
from rest_framework.routers import DefaultRouter

from users.views import TransferSystemBot,DashboardView

##فقط اكتب الرابط في المتصفح لرؤوية جميع الروابط##
# http://127.0.0.1:8000/user/api/docs/

router = DefaultRouter()
router.register(r'notifications', views.NotificationViewSet, basename='notification')
router.register(r'workspaces', views.WorkspaceViewSet, basename='workspace')
router.register(r'projects', views.ProjectViewSet, basename='project')
router.register(r'invitations', views.InvitationViewSet, basename='invitation')
router.register(r'searchUser', views.searchUserViewSet, basename='search-user')
router.register(r'TaskView', views.TaskView, basename='TaskView')


#router.register(r'TransferSystemBot', views.TransferSystemBot, basename='Transfer')

urlpatterns = [

    # path('login/', views.Token.as_view()),
    path('api/schema/', SpectacularAPIView.as_view(), name='schema'),
    path('api/docs/', SpectacularSwaggerView.as_view(url_name='schema'), name='swagger-ui'),

    path('projects/<int:project_id>/transfer-tasks/', TransferSystemBot.as_view(), name='transfer-tasks'),
    path('dashboard/', DashboardView.as_view(), name='dashboard-main'),

    path('api/', include(router.urls)),


]


# Django Allauth:

# Authentication URLs:
# /accounts/login/            → تسجيل الدخول
# /accounts/logout/           → تسجيل الخروج
# /accounts/signup/           → إنشاء حساب جديد
# /accounts/password/change/  → تغيير كلمة المرور
# /accounts/password/set/     → تعيين كلمة مرور

# Password reset:
# /accounts/password/reset/           → طلب إعادة تعيين كلمة المرور
# /accounts/password/reset/done/      → تم إرسال رابط إعادة التعيين
# /accounts/password/reset/key/<key>/ → إعادة تعيين كلمة المرور

# Social Login (OAuth):
# /accounts/google/login/      → Googleتسجيل الدخول عبر
# /accounts/google/login/callback/ → رجوع __Google بعد تسجيل الدخول

# /accounts/github/login/      → GitHub تسجيل الدخول عبر
# /accounts/github/login/callback/ → رجوع __GitHub بعد تسجيل الدخول

# General:
# /accounts/confirm-email/     → تأكيد البريد الإلكتروني (إن تم تفعيله)
# /accounts/inactive/          → حساب غير مفعل