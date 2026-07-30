from rest_framework import status, viewsets
from rest_framework.decorators import action
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from users.models import LeaveTaskAction, ProjectRole
from users.serializers.report import LeaveTaskActionSerializer

from rest_framework import status, viewsets
from rest_framework.decorators import action
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from users.models import LeaveTaskAction, ProjectRole
from users.serializers.report import (
    LeaveTaskActionSerializer,
    ResolveLeaveTaskActionSerializer,
)
from users.services.leave_service import LeaveRequestService
from users.errors.messages.success import success_response
class LeaveTaskActionViewSet(viewsets.ReadOnlyModelViewSet):
    permission_classes = [IsAuthenticated]
    serializer_class = LeaveTaskActionSerializer

    def get_queryset(self):
        user = self.request.user

        managed_projects = ProjectRole.objects.filter(
            user=user,
            role__in=["ADMIN", "MANAGER"],
        ).values_list(
            "project_id",
            flat=True,
        )

        return LeaveTaskAction.objects.filter(
            request__project_id__in=managed_projects,
        ).select_related(
            "request",
            "request__user",
            "task",
            "task__assigned_to",
            "new_assignee",
            "resolved_by",
        )

    @action(
        detail=True,
        methods=["patch"],
        url_path="resolve",
    )
    def resolve(self, request, pk=None):
        leave_action = self.get_object()

        serializer = ResolveLeaveTaskActionSerializer(
            data=request.data,
            context={
                "request": request,
                "leave_action": leave_action,
            },
        )

        serializer.is_valid(raise_exception=True)

        leave_action = LeaveRequestService.resolve_task_action(
            leave_action=leave_action,
            manager_user=request.user,
            validated_data=serializer.validated_data,
        )

        response_serializer = LeaveTaskActionSerializer(
            leave_action,
            context={
                "request": request,
            },
        )

        return Response(
            success_response(
                message="LEAVE_TASK_ACTION_RESOLVED",
                code="LEAVE_TASK_ACTION_RESOLVED",
                data=response_serializer.data,
            ),
            status=status.HTTP_200_OK,
        )