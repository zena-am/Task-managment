#from rest_framework_simplejwt.views import TokenObtainPairView, TokenRefreshView
from django.urls import include, path
from users import views
from drf_spectacular.utils import extend_schema
from drf_spectacular.views import SpectacularAPIView, SpectacularSwaggerView
from rest_framework.routers import DefaultRouter

from users.views import TransferSystemBot,DashboardView
from users.views.members_views import ProjectMemberViewSet, WorkSpaceMemberViewSet
from users.views.report import RequestFormViewSet, TechnicalReportViewSet
from users.views.tasks import  ClaimTaskAPIView, ReviewTechnicalReportAPIView, TaskStatusUpdateAPIView, TransferTaskToUser
from users.views.workspaces import LeaveWorkspaceAPIView, TogglePinWorkspaceAPIView, WorkspaceViewSet

##فقط اكتب الرابط في المتصفح لرؤوية جميع الروابط##
# http://127.0.0.1:8000/user/api/docs/

from rest_framework_nested.routers import NestedDefaultRouter

router = DefaultRouter()
from users.views.projects import ProjectViewSet

router = DefaultRouter()
router.register(r'projects', ProjectViewSet, basename='projects')
router.register('workspace',WorkSpaceMemberViewSet,basename='workspace-members')

project_router = NestedDefaultRouter(router,r'projects',lookup='project')
workspace_router = NestedDefaultRouter(router,r'workspace',lookup='workspace')

project_router.register(r'members',ProjectMemberViewSet,basename='project-members')
workspace_router.register(r'members',WorkSpaceMemberViewSet,basename='workspace-members')


router.register(r'notifications', views.NotificationViewSet, basename='notification')
router.register(r'workspaces', views.WorkspaceViewSet, basename='workspace')
router.register(r'projects', views.ProjectViewSet, basename='project')
router.register(r'invitations', views.InvitationViewSet, basename='invitation')
router.register(r'searchUser', views.searchUserViewSet, basename='search-user')
router.register(r'TaskView', views.TaskView, basename='TaskView')
#router.register('workspace-members',WorkSpaceMemberViewSet,basename='workspace-members')
router.register(r'technical-reports', TechnicalReportViewSet)
router.register(r'requests', RequestFormViewSet)
#router.register(r'requests', ReviewRequestFormAPIView)

urlpatterns = [
    path('', include(router.urls)),
    path('', include(project_router.urls)),
    path('', include(workspace_router.urls)),

    path('api/schema/', SpectacularAPIView.as_view(), name='schema'),
    path('api/docs/', SpectacularSwaggerView.as_view(url_name='schema'), name='swagger-ui'),

    path('projects/<int:project_id>/assigned-tasks/', TransferTaskToUser.as_view(), name='assignedtouser'),
    path('projects/<int:project_id>/assigned-project/', TransferSystemBot.as_view(), name='assignmanager'),

    path("tasks/<int:task_id>/review-report/",ReviewTechnicalReportAPIView.as_view(),name="review-technical-report"),
    path("tasks/<int:task_id>/status-update/",TaskStatusUpdateAPIView.as_view(),name="task-status-update"),
    path("tasks/<int:task_id>/claim/",ClaimTaskAPIView.as_view(),name="claim-task"),
    path("workspaces/<int:workspace_id>/toggle-pin/",TogglePinWorkspaceAPIView.as_view(),name="workspace-toggle-pin"),
    path("workspaces/<int:workspace_id>/leave/",LeaveWorkspaceAPIView.as_view(),name="workspace-leave"),
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