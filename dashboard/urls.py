from django.urls import path

from .views import (
    ManagerDashboardActivityView,
    ManagerDashboardChartsView,
    ManagerDashboardOverviewView,
    ManagerEmployeePerformanceView,
    ManagerPerformanceView,
    ManagerProjectPerformanceView,
    ManagerWorkspacePerformanceView,
    ManagerBulkTaskActionView,
    ManagerDashboardExportView,
    ManagerArchiveActionView,
)

app_name = "dashboard"

urlpatterns = [
    path("overview/", ManagerDashboardOverviewView.as_view(), name="overview"),
    path("activity/", ManagerDashboardActivityView.as_view(), name="activity"),
    path("performance/", ManagerPerformanceView.as_view(), name="performance"),
    path(
        "performance/employees/<int:employee_id>/",
        ManagerEmployeePerformanceView.as_view(),
        name="employee-performance",
    ),
    path(
        "performance/workspaces/<int:workspace_id>/",
        ManagerWorkspacePerformanceView.as_view(),
        name="workspace-performance",
    ),
    path(
        "performance/projects/<int:project_id>/",
        ManagerProjectPerformanceView.as_view(),
        name="project-performance",
    ),
    path("charts/", ManagerDashboardChartsView.as_view(), name="charts"),
    path("tasks/bulk-action/", ManagerBulkTaskActionView.as_view(), name="bulk-task-action"),
    path("export/", ManagerDashboardExportView.as_view(), name="export"),
    path("archive/<str:resource>/<int:object_id>/", ManagerArchiveActionView.as_view(), name="archive-action"),
]
