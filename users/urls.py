#from rest_framework_simplejwt.views import TokenObtainPairView, TokenRefreshView
from django.urls import include, path
from users import views
from .views import update_profile

urlpatterns = [
    # path('login/', views.Token.as_view()),



    path('profilo/', views.profile,name='profilo'),
    path('update_profile/', views.update_profile,name='update_profile'),




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