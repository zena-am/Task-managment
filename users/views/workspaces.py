from datetime import timedelta

from django.shortcuts import get_object_or_404
from django.utils import timezone
from rest_framework import viewsets, permissions, status
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework.exceptions import PermissionDenied
from drf_spectacular.utils import extend_schema, extend_schema_view
from rest_framework.views import APIView
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework import serializers
from django.utils.dateparse import parse_datetime
from users.models import Project
from users.services.working_time_service import WorkingTimeService
from users.services.task_service import (
    calculate_employee_task_availability,
    calculate_workspace_task_schedule,
)
from users.errors.exceptions import BaseAppException, PermissionDeniedError
from users.errors.messages.success import success_response
from users.services.WorkspaceService import WorkspaceServices
from users.constants import create_activity_log
from ..models import RequestForm, Task, User, WorkSpace, WorkSpaceMember
from ..serializers import WorkSpaceSerializer, WorkSpaceCreateSerializer
from ..permissions import IsWorkspaceOwnerOrReadOnly
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from users.models import WorkspaceWorkingSchedule
from users.serializers import WorkspaceWorkingScheduleSerializer
@extend_schema_view(
    list=extend_schema(tags=['فضاءات العمل'], summary="عرض فضاءات العمل الخاصة بالمستخدم مرتبة حسب التثبيت"),
    create=extend_schema(tags=['فضاءات العمل'], summary="إنشاء فضاء عمل جديد"),
    retrieve=extend_schema(tags=['فضاءات العمل'], summary="جلب تفاصيل فضاء عمل محدد"),
    update=extend_schema(tags=['فضاءات العمل'], summary="(للمالك) تحديث كامل لفضاء العمل"),
    destroy=extend_schema(tags=['فضاءات العمل'], summary="(للمدير) حذف فضاء العمل"),
)
class WorkspaceViewSet(viewsets.ModelViewSet):
    permission_classes = [permissions.IsAuthenticated]

    def get_serializer_class(self):
        if self.action in ['create', 'update', 'partial_update']:
            return WorkSpaceCreateSerializer
        return WorkSpaceSerializer

    def get_queryset(self):
        return WorkspaceServices.get_user_workspaces(self.request.user)

    def create(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        result = WorkspaceServices.create_workspace(
            serializer=serializer,
            user=request.user,
            data=request.data,
        )
        response_serializer = WorkSpaceSerializer(
            result['workspace'],
            context=self.get_serializer_context(),
        )
        return Response(success_response(
            message="Workspace created successfully",
            code="WORKSPACE_CREATED",
            data={
                "workspace": response_serializer.data,
                "invitations_result": result.get("invitations_result"),
            },
        ), status=status.HTTP_201_CREATED)

    def update(self, request, *args, **kwargs):
        partial = kwargs.pop('partial', False)
        instance = self.get_object()

        if instance.creator_id != request.user.id:
            raise PermissionDeniedError()

        serializer = self.get_serializer(instance, data=request.data, partial=partial)
        serializer.is_valid(raise_exception=True)
        result = WorkspaceServices.update_workspace(
            serializer=serializer,
            user=request.user,
            data=request.data,
        )
        response_serializer = WorkSpaceSerializer(
            result['workspace'],
            context=self.get_serializer_context(),
        )
        return Response(success_response(
            message="Workspace updated successfully",
            code="WORKSPACE_UPDATED",
            data={
                "workspace": response_serializer.data,
                "invitations_result": result.get("invitations_result"),
            },
        ), status=status.HTTP_200_OK)

    def partial_update(self, request, *args, **kwargs):
        kwargs['partial'] = True
        return self.update(request, *args, **kwargs)

    def destroy(self, request, *args, **kwargs):
        workspace = self.get_object()

        if workspace.creator_id != request.user.id:
            raise PermissionDeniedError()

        workspace_id = workspace.id
        workspace_name = workspace.name
        self.perform_destroy(workspace)
        create_activity_log(user=request.user, action="WORKSPACE_DELETED", action_id=workspace_id, changes={"target_title": workspace_name, "reason": "Workspace deleted"})
        return Response(success_response(
            message="Workspace deleted successfully",
            code="WORKSPACE_DELETED",
            data={"workspace_id": workspace_id},
        ), status=status.HTTP_200_OK)

    @extend_schema(tags=['الفضاءات'], summary="نقل ملكية")
    @action(detail=True, methods=['post'], url_path='transfer')
    def transfer_owner(self, request, pk=None):
        new_owner_id = request.data.get("new_owner_id")

        if not new_owner_id:
            raise BaseAppException(
                detail="new_owner_id is required",
                code="NEW_OWNER_REQUIRED",
                status_code=400,
            )

        try:
            new_owner_id = int(new_owner_id)
        except (TypeError, ValueError):
            raise BaseAppException(
                detail="new_owner_id must be a valid integer",
                code="INVALID_NEW_OWNER_ID",
                status_code=400,
            )

        workspace = self.get_object()
        new_owner = get_object_or_404(User, id=new_owner_id)

        if workspace.creator_id == new_owner_id:
            raise BaseAppException(
                detail="You are already the owner",
                code="ALREADY_OWNER",
                status_code=400,
            )

        if workspace.creator != request.user:
            raise PermissionDeniedError()

        if not WorkSpaceMember.objects.filter(workspace=workspace, user=new_owner).exists():
            raise BaseAppException(
                detail="User is not a member of this workspace",
                code="USER_NOT_IN_WORKSPACE",
                status_code=400,
            )

        result = WorkspaceServices.transfer_ownership(workspace, new_owner)

        return Response(success_response(
            message="Ownership transferred successfully",
            code="WORKSPACE_OWNERSHIP_TRANSFERRED",
            data=result,
        ), status=status.HTTP_200_OK)


class TogglePinWorkspaceAPIView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    @extend_schema(
        tags=['فضاءات العمل'],
        summary="(للموظف) تثبيت أو إلغاء تثبيت فضاء العمل",
    )
    def post(self, request, workspace_id):
        workspace = get_object_or_404(WorkSpace, id=workspace_id, members=request.user)
        result = WorkspaceServices.toggle_pin(user=request.user, workspace=workspace)

        return Response(success_response(
            message="Workspace pin updated successfully",
            code="WORKSPACE_PIN_UPDATED",
            data=result,
        ), status=status.HTTP_200_OK)


class LeaveWorkspaceAPIView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    @extend_schema(
        tags=['فضاءات العمل'],
        summary="(للموظف) مغادرة فضاء العمل",
    )
    def delete(self, request, workspace_id):
        workspace = get_object_or_404(WorkSpace, id=workspace_id, members=request.user)
        result = WorkspaceServices.leave_workspace(user=request.user, workspace=workspace)

        return Response(success_response(
            message="Left workspace successfully",
            code="WORKSPACE_LEFT",
            data=result,
        ), status=status.HTTP_200_OK)


class WorkspaceWorkingScheduleView(APIView):

    permission_classes = [IsAuthenticated]

    def get(self, request, workspace_id):

        schedule = WorkspaceWorkingSchedule.objects.get(
            workspace_id=workspace_id
        )

        serializer = WorkspaceWorkingScheduleSerializer(
            schedule
        )

        return Response(serializer.data)


    def patch(self, request, workspace_id):
        workspace = WorkSpace.objects.get(
            id=workspace_id
        )

        is_owner = (
            workspace.creator_id == request.user.id
        )

        is_admin = WorkSpaceMember.objects.filter(
            workspace=workspace,
            user=request.user,
            role="ADMIN",
        ).exists()


        if not (is_owner or is_admin):
            raise PermissionDenied(
                "You do not have permission to update workspace schedule."
            )
        schedule = WorkspaceWorkingSchedule.objects.get(
            workspace_id=workspace_id
        )

        serializer = WorkspaceWorkingScheduleSerializer(
            schedule,
            data=request.data,
            partial=True
        )

        serializer.is_valid(
            raise_exception=True
        )

        serializer.save()

        return Response(
            serializer.data
        )









class TaskWorkingTimeCheckAPIView(APIView):

    permission_classes = [IsAuthenticated]

    def post(self, request):
        project_id = request.data.get("project")
        employee_id = request.data.get("employee")
        expected_hours = request.data.get("expected_hours")
        due_date_value = request.data.get("due_date")
        task_id = request.data.get("task_id")

        if not project_id:
            raise serializers.ValidationError({
                "project": "Project is required."
            })

        if expected_hours in [None, ""]:
            raise serializers.ValidationError({
                "expected_hours": "Expected hours are required."
            })

        try:
            expected_hours = float(expected_hours)
        except (TypeError, ValueError):
            raise serializers.ValidationError({
                "expected_hours": "Expected hours must be a number."
            })

        if expected_hours <= 0:
            raise serializers.ValidationError({
                "expected_hours": "Expected hours must be greater than zero."
            })

        due_date = parse_datetime(due_date_value or "")
        if not due_date:
            raise serializers.ValidationError({
                "due_date": "Invalid datetime format."
            })

        if timezone.is_naive(due_date):
            due_date = timezone.make_aware(
                due_date,
                timezone.get_current_timezone(),
            )

        project = get_object_or_404(Project, id=project_id)

        actual_duration = timedelta(0)
        if task_id:
            task = get_object_or_404(Task, id=task_id)
            actual_duration = task.actual_duration or timedelta(0)

        if employee_id:
            employee = get_object_or_404(User, id=employee_id)
            result = calculate_employee_task_availability(
                employee=employee,
                project=project,
                due_date=due_date,
                expected_duration=timedelta(hours=expected_hours),
                actual_duration=actual_duration,
                start_datetime=timezone.now(),
                task_id=task_id,
                include_suggestion=True,
            )
            message = "The selected due date is feasible."
            if not result["valid"]:
                if result.get("reason") == "DUE_DATE_OUTSIDE_WORKING_SCHEDULE":
                    message = (
                        "The selected due date is outside the workspace working "
                        "schedule."
                    )
                else:
                    message = (
                        "The selected due date is not feasible for this employee "
                        "after considering workspace workload and project leave periods."
                    )
            elif result.get("deadline_during_leave"):
                message = (
                    "The deadline falls during approved project leave, but the task "
                    "can still be completed within the available working time."
                )
        else:
            result = calculate_workspace_task_schedule(
                project=project,
                due_date=due_date,
                expected_duration=timedelta(hours=expected_hours),
                start_datetime=timezone.now(),
            )
            result.setdefault("workspace_remaining_workload_hours", 0.0)
            result.setdefault("deadline_during_leave", False)
            result.setdefault("approved_leave_intervals", [])
            result.setdefault("pending_leave_warnings", [])
            result.setdefault("affected_tasks", [])
            result.setdefault("existing_conflicts", [])
            result.setdefault("candidate_valid", result["valid"])

            if result["valid"]:
                message = (
                    "The selected due date matches the workspace working schedule. "
                    "Employee capacity will be checked after assignment."
                )
            elif result.get("reason") == "DUE_DATE_OUTSIDE_WORKING_SCHEDULE":
                message = (
                    "The selected due date is outside the workspace working schedule."
                )
            else:
                message = (
                    "The selected due date does not provide enough workspace working "
                    "hours for this task."
                )

        return Response({
            "valid": result["valid"],
            "reason": result.get("reason"),
            "required_hours": result.get("required_hours", 0),
            "remaining_required_hours": result.get(
                "remaining_required_hours",
                result.get("required_hours", 0),
            ),
            "available_hours": result.get("available_hours", 0),
            "deficit_hours": result.get("deficit_hours", 0),
            "overbooked_hours": result.get("deficit_hours", 0),
            "workspace_remaining_workload_hours": result.get(
                "workspace_remaining_workload_hours",
                0,
            ),
            "deadline_during_leave": result.get(
                "deadline_during_leave",
                False,
            ),
            "approved_leave_intervals": result.get(
                "approved_leave_intervals",
                [],
            ),
            "pending_leave_warnings": result.get(
                "pending_leave_warnings",
                [],
            ),
            "affected_tasks": result.get("affected_tasks", []),
            "existing_conflicts": result.get("existing_conflicts", []),
            "candidate_valid": result.get("candidate_valid", result["valid"]),
            "message": message,
            "suggested_due_date": result.get("suggested_due_date"),
        })
