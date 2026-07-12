from django.urls import include, path
from drf_spectacular.views import SpectacularAPIView, SpectacularSwaggerView
from rest_framework.routers import DefaultRouter
from rest_framework_nested.routers import NestedDefaultRouter

from users.views import DashboardView, InvitationViewSet, NotificationViewSet, ProjectViewSet, searchUserViewSet, TaskView, TransferSystemBot
from users.views.invitations import invitationsMembers
from users.views.members_views import ProjectMemberViewSet, WorkSpaceMemberViewSet
from users.views.profile import ProfileView
from users.views.report import BugReportViewSet, RequestFormViewSet, TechnicalReportViewSet
from users.views.searchItems import ProjectSearchViewSet, WorkspaceSearchViewSet
from users.views.tasks import ClaimTaskAPIView, ReviewTechnicalReportAPIView, TaskStatusUpdateAPIView, TransferTaskToUser
from users.views.workspaces import LeaveWorkspaceAPIView, TogglePinWorkspaceAPIView, WorkspaceViewSet

##[http://127.0.0.1:8000/user/api/docs/](http://127.0.0.1:8000/api/docs/)
router = DefaultRouter()
router.register(r'workspaces', WorkspaceViewSet, basename='workspace')
router.register(r'projects', ProjectViewSet, basename='project')
router.register(r'notifications', NotificationViewSet, basename='notification')
router.register(r'invitations', InvitationViewSet, basename='invitation')
router.register(r'invitation-management', invitationsMembers, basename='invitation-management')
router.register(r'searchUser', searchUserViewSet, basename='search-user')
router.register(r'TaskView', TaskView, basename='TaskView')
router.register(r'technical-reports', TechnicalReportViewSet, basename='technical-report')
router.register(r'requests', RequestFormViewSet, basename='request')
router.register(r'bug-reports', BugReportViewSet, basename='bug-report')
router.register(r"workspace-search",WorkspaceSearchViewSet,basename="workspace-search",)

router.register(r"project-search",ProjectSearchViewSet,basename="project-search",)
project_router = NestedDefaultRouter(router, r'projects', lookup='project')
project_router.register(r'members', ProjectMemberViewSet, basename='project-members')

workspace_router = NestedDefaultRouter(router, r'workspaces', lookup='workspace')
workspace_router.register(r'members', WorkSpaceMemberViewSet, basename='workspace-members')

urlpatterns = [
    path('', include(router.urls)),
    path('', include(project_router.urls)),
    path('', include(workspace_router.urls)),
    path("api/profile/", ProfileView.as_view(), name="profile"),

    path('api/schema/', SpectacularAPIView.as_view(), name='schema'),
    path('api/docs/', SpectacularSwaggerView.as_view(url_name='schema'), name='swagger-ui'),

    path('projects/<int:project_id>/tasks/<int:task_id>/assign/', TransferTaskToUser.as_view(), name='assign-task-to-user'),
    path('projects/<int:project_id>/unassigned-tasks/', TransferTaskToUser.as_view(), name='unassigned-project-tasks'),
    path('projects/<int:project_id>/assigned-project/', TransferSystemBot.as_view(), name='assignmanager'),

    path('tasks/<int:task_id>/review-report/', ReviewTechnicalReportAPIView.as_view(), name='review-technical-report'),
    path('tasks/<int:task_id>/status-update/', TaskStatusUpdateAPIView.as_view(), name='task-status-update'),
    path('tasks/<int:task_id>/claim/', ClaimTaskAPIView.as_view(), name='claim-task'),
    path('workspaces/<int:workspace_id>/toggle-pin/', TogglePinWorkspaceAPIView.as_view(), name='workspace-toggle-pin'),
    path('workspaces/<int:workspace_id>/leave/', LeaveWorkspaceAPIView.as_view(), name='workspace-leave'),
    path('dashboard/', DashboardView.as_view(), name='dashboard-main'),

    # Compatibility prefix if the frontend already uses /api/ inside this app include.
    path('api/', include(router.urls)),
    path('api/', include(project_router.urls)),
    path('api/', include(workspace_router.urls)),
]
