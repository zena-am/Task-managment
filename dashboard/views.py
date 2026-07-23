from django.utils.dateparse import parse_date
from drf_spectacular.utils import OpenApiParameter, extend_schema
from rest_framework import status
from rest_framework.exceptions import NotFound, ValidationError
from rest_framework.pagination import PageNumberPagination
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from users.errors.messages.success import success_response

from .permissions import IsDashboardManager
from .selectors import (
    get_activity_queryset,
    get_overview,
    validate_workspace_access,
)
from .serializers import ActivityLogSerializer, DashboardOverviewSerializer


class DashboardPagination(PageNumberPagination):
    page_size = 20
    page_size_query_param = "page_size"
    max_page_size = 100


class ManagerDashboardOverviewView(APIView):
    permission_classes = [IsAuthenticated, IsDashboardManager]

    @extend_schema(
        tags=["Manager Dashboard"],
        summary="Manager dashboard overview",
        parameters=[
            OpenApiParameter("workspace_id", int, required=False),
        ],
        responses={200: DashboardOverviewSerializer},
    )
    def get(self, request):
        workspace_id = request.query_params.get("workspace_id")
        workspace = None
        if workspace_id:
            if not workspace_id.isdigit():
                raise ValidationError({"workspace_id": "Must be a valid integer."})
            workspace = validate_workspace_access(request.user, int(workspace_id))
            if workspace is None:
                raise NotFound("Workspace was not found or you cannot manage it.")

        data = get_overview(request.user, workspace)
        serializer = DashboardOverviewSerializer(data)
        return Response(
            success_response(
                message="Manager dashboard overview retrieved successfully",
                code="MANAGER_DASHBOARD_OVERVIEW_RETRIEVED",
                data=serializer.data,
            ),
            status=status.HTTP_200_OK,
        )


class ManagerDashboardActivityView(APIView):
    permission_classes = [IsAuthenticated, IsDashboardManager]
    pagination_class = DashboardPagination

    @extend_schema(
        tags=["Manager Dashboard"],
        summary="Manager activity history",
        parameters=[
            OpenApiParameter("workspace_id", int, required=False),
            OpenApiParameter("employee_id", int, required=False),
            OpenApiParameter("action", str, required=False),
            OpenApiParameter("date_from", str, required=False, description="YYYY-MM-DD"),
            OpenApiParameter("date_to", str, required=False, description="YYYY-MM-DD"),
            OpenApiParameter("page", int, required=False),
            OpenApiParameter("page_size", int, required=False),
        ],
        responses={200: ActivityLogSerializer(many=True)},
    )
    def get(self, request):
        workspace_id = request.query_params.get("workspace_id")
        employee_id = request.query_params.get("employee_id")
        workspace = None

        if workspace_id:
            if not workspace_id.isdigit():
                raise ValidationError({"workspace_id": "Must be a valid integer."})
            workspace = validate_workspace_access(request.user, int(workspace_id))
            if workspace is None:
                raise NotFound("Workspace was not found or you cannot manage it.")

        if employee_id and not employee_id.isdigit():
            raise ValidationError({"employee_id": "Must be a valid integer."})

        date_from_raw = request.query_params.get("date_from")
        date_to_raw = request.query_params.get("date_to")
        date_from = parse_date(date_from_raw) if date_from_raw else None
        date_to = parse_date(date_to_raw) if date_to_raw else None
        if date_from_raw and date_from is None:
            raise ValidationError({"date_from": "Use YYYY-MM-DD format."})
        if date_to_raw and date_to is None:
            raise ValidationError({"date_to": "Use YYYY-MM-DD format."})
        if date_from and date_to and date_from > date_to:
            raise ValidationError({"date_to": "Must be on or after date_from."})

        queryset = get_activity_queryset(
            user=request.user,
            workspace=workspace,
            employee_id=int(employee_id) if employee_id else None,
            action=request.query_params.get("action"),
            date_from=date_from,
            date_to=date_to,
        )

        paginator = self.pagination_class()
        page = paginator.paginate_queryset(queryset, request, view=self)
        serializer = ActivityLogSerializer(page, many=True)
        paginated = paginator.get_paginated_response(serializer.data).data

        return Response(
            success_response(
                message="Activity history retrieved successfully",
                code="MANAGER_DASHBOARD_ACTIVITY_RETRIEVED",
                data=paginated,
            ),
            status=status.HTTP_200_OK,
        )

from .performance import (
    get_charts,
    get_employee_performance,
    get_performance,
    validate_project_access,
)
from .serializers import (
    DashboardChartsSerializer,
    EmployeePerformanceSerializer,
    PerformanceListSerializer,
    PerformanceQuerySerializer,
)


def _resolve_performance_scope(user, params):
    workspace = None
    project = None
    workspace_id = params.get("workspace_id")
    project_id = params.get("project_id")

    if workspace_id:
        workspace = validate_workspace_access(user, workspace_id)
        if workspace is None:
            raise NotFound("Workspace was not found or you cannot manage it.")

    if project_id:
        project = validate_project_access(user, project_id)
        if project is None:
            raise NotFound("Project was not found or you cannot manage it.")
        if workspace is not None and project.workspace_id != workspace.id:
            raise ValidationError({"project_id": "The project does not belong to the selected workspace."})
        if workspace is None and project.workspace_id:
            workspace = project.workspace

    return workspace, project


class ManagerPerformanceView(APIView):
    permission_classes = [IsAuthenticated, IsDashboardManager]

    @extend_schema(
        tags=["Manager Dashboard"],
        summary="Employee performance across managed workspaces and projects",
        parameters=[
            OpenApiParameter("workspace_id", int, required=False),
            OpenApiParameter("project_id", int, required=False),
            OpenApiParameter("employee_id", int, required=False),
            OpenApiParameter("date_from", str, required=False, description="YYYY-MM-DD"),
            OpenApiParameter("date_to", str, required=False, description="YYYY-MM-DD"),
        ],
        responses={200: PerformanceListSerializer},
    )
    def get(self, request):
        query = PerformanceQuerySerializer(data=request.query_params)
        query.is_valid(raise_exception=True)
        params = query.validated_data
        workspace, project = _resolve_performance_scope(request.user, params)

        data = get_performance(
            user=request.user,
            workspace=workspace,
            project=project,
            employee_id=params.get("employee_id"),
            date_from=params.get("date_from"),
            date_to=params.get("date_to"),
        )
        serializer = PerformanceListSerializer(data)
        return Response(
            success_response(
                message="Employee performance retrieved successfully",
                code="MANAGER_PERFORMANCE_RETRIEVED",
                data=serializer.data,
            ),
            status=status.HTTP_200_OK,
        )


class ManagerEmployeePerformanceView(APIView):
    permission_classes = [IsAuthenticated, IsDashboardManager]

    @extend_schema(
        tags=["Manager Dashboard"],
        summary="Detailed performance for one employee",
        parameters=[
            OpenApiParameter("workspace_id", int, required=False),
            OpenApiParameter("project_id", int, required=False),
            OpenApiParameter("date_from", str, required=False, description="YYYY-MM-DD"),
            OpenApiParameter("date_to", str, required=False, description="YYYY-MM-DD"),
        ],
        responses={200: EmployeePerformanceSerializer},
    )
    def get(self, request, employee_id):
        raw = request.query_params.copy()
        raw["employee_id"] = employee_id
        query = PerformanceQuerySerializer(data=raw)
        query.is_valid(raise_exception=True)
        params = query.validated_data
        workspace, project = _resolve_performance_scope(request.user, params)

        data = get_employee_performance(
            user=request.user,
            employee_id=employee_id,
            workspace=workspace,
            project=project,
            date_from=params.get("date_from"),
            date_to=params.get("date_to"),
        )
        if data is None:
            raise NotFound("Employee was not found in the selected manageable scope.")

        serializer = EmployeePerformanceSerializer(data)
        return Response(
            success_response(
                message="Employee performance retrieved successfully",
                code="MANAGER_EMPLOYEE_PERFORMANCE_RETRIEVED",
                data=serializer.data,
            ),
            status=status.HTTP_200_OK,
        )


class ManagerWorkspacePerformanceView(APIView):
    permission_classes = [IsAuthenticated, IsDashboardManager]

    @extend_schema(
        tags=["Manager Dashboard"],
        summary="Performance for one workspace",
        responses={200: PerformanceListSerializer},
    )
    def get(self, request, workspace_id):
        raw = request.query_params.copy()
        raw["workspace_id"] = workspace_id
        query = PerformanceQuerySerializer(data=raw)
        query.is_valid(raise_exception=True)
        params = query.validated_data
        workspace, project = _resolve_performance_scope(request.user, params)
        data = get_performance(
            request.user,
            workspace=workspace,
            project=project,
            employee_id=params.get("employee_id"),
            date_from=params.get("date_from"),
            date_to=params.get("date_to"),
        )
        return Response(
            success_response(
                message="Workspace performance retrieved successfully",
                code="MANAGER_WORKSPACE_PERFORMANCE_RETRIEVED",
                data=PerformanceListSerializer(data).data,
            )
        )


class ManagerProjectPerformanceView(APIView):
    permission_classes = [IsAuthenticated, IsDashboardManager]

    @extend_schema(
        tags=["Manager Dashboard"],
        summary="Performance for one project",
        responses={200: PerformanceListSerializer},
    )
    def get(self, request, project_id):
        raw = request.query_params.copy()
        raw["project_id"] = project_id
        query = PerformanceQuerySerializer(data=raw)
        query.is_valid(raise_exception=True)
        params = query.validated_data
        workspace, project = _resolve_performance_scope(request.user, params)
        data = get_performance(
            request.user,
            workspace=workspace,
            project=project,
            employee_id=params.get("employee_id"),
            date_from=params.get("date_from"),
            date_to=params.get("date_to"),
        )
        return Response(
            success_response(
                message="Project performance retrieved successfully",
                code="MANAGER_PROJECT_PERFORMANCE_RETRIEVED",
                data=PerformanceListSerializer(data).data,
            )
        )


class ManagerDashboardChartsView(APIView):
    permission_classes = [IsAuthenticated, IsDashboardManager]

    @extend_schema(
        tags=["Manager Dashboard"],
        summary="Chart-ready manager dashboard data",
        parameters=[
            OpenApiParameter("workspace_id", int, required=False),
            OpenApiParameter("project_id", int, required=False),
            OpenApiParameter("employee_id", int, required=False),
            OpenApiParameter("date_from", str, required=False, description="YYYY-MM-DD"),
            OpenApiParameter("date_to", str, required=False, description="YYYY-MM-DD"),
        ],
        responses={200: DashboardChartsSerializer},
    )
    def get(self, request):
        query = PerformanceQuerySerializer(data=request.query_params)
        query.is_valid(raise_exception=True)
        params = query.validated_data
        workspace, project = _resolve_performance_scope(request.user, params)

        data = get_charts(
            request.user,
            workspace=workspace,
            project=project,
            employee_id=params.get("employee_id"),
            date_from=params.get("date_from"),
            date_to=params.get("date_to"),
        )
        return Response(
            success_response(
                message="Dashboard charts retrieved successfully",
                code="MANAGER_DASHBOARD_CHARTS_RETRIEVED",
                data=DashboardChartsSerializer(data).data,
            ),
            status=status.HTTP_200_OK,
        )

from .exports import csv_response, export_queryset, pdf_response, xlsx_response
from .serializers import ArchiveActionSerializer, BulkTaskActionSerializer, ExportQuerySerializer
from .services import bulk_update_tasks, set_archive_state


class ManagerBulkTaskActionView(APIView):
    permission_classes = [IsAuthenticated, IsDashboardManager]

    @extend_schema(
        tags=["Manager Dashboard"],
        summary="Apply one action to multiple managed tasks",
        request=BulkTaskActionSerializer,
    )
    def post(self, request):
        serializer = BulkTaskActionSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = bulk_update_tasks(request.user, serializer.validated_data)
        return Response(
            success_response(
                message="Bulk task action completed successfully",
                code="BULK_TASK_ACTION_COMPLETED",
                data=data,
            ),
            status=status.HTTP_200_OK,
        )


class ManagerDashboardExportView(APIView):
    permission_classes = [IsAuthenticated, IsDashboardManager]

    @extend_schema(
        tags=["Manager Dashboard"],
        summary="Export managed tasks or reports as CSV, XLSX, or PDF",
        parameters=[
            OpenApiParameter("resource", str, required=False, description="tasks or reports"),
            OpenApiParameter("format", str, required=False, description="csv, xlsx, or pdf"),
            OpenApiParameter("workspace_id", int, required=False),
            OpenApiParameter("project_id", int, required=False),
            OpenApiParameter("employee_id", int, required=False),
            OpenApiParameter("date_from", str, required=False),
            OpenApiParameter("date_to", str, required=False),
            OpenApiParameter("include_archived", bool, required=False),
        ],
    )
    def get(self, request):
        serializer = ExportQuerySerializer(data=request.query_params)
        serializer.is_valid(raise_exception=True)
        params = serializer.validated_data
        workspace, project = _resolve_performance_scope(request.user, params)
        queryset = export_queryset(
            user=request.user,
            resource=params["resource"],
            workspace=workspace,
            project=project,
            employee_id=params.get("employee_id"),
            date_from=params.get("date_from"),
            date_to=params.get("date_to"),
            include_archived=params.get("include_archived", False),
        )
        export_format = params["format"]
        if export_format == "xlsx":
            return xlsx_response(params["resource"], queryset)
        if export_format == "pdf":
            return pdf_response(params["resource"], queryset)
        return csv_response(params["resource"], queryset)


class ManagerArchiveActionView(APIView):
    permission_classes = [IsAuthenticated, IsDashboardManager]

    @extend_schema(
        tags=["Manager Dashboard"],
        summary="Archive or restore a managed workspace, project, or task",
        request=ArchiveActionSerializer,
    )
    def post(self, request, resource, object_id):
        if resource not in ("workspace", "project", "task"):
            raise ValidationError({"resource": "Use workspace, project, or task."})
        serializer = ArchiveActionSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = set_archive_state(
            request.user,
            resource,
            object_id,
            serializer.validated_data["archive"],
        )
        return Response(
            success_response(
                message="Archive state updated successfully",
                code="ARCHIVE_STATE_UPDATED",
                data=data,
            ),
            status=status.HTTP_200_OK,
        )
