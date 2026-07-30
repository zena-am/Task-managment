
from django.shortcuts import get_object_or_404

from rest_framework import status
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView
from users.models import Task
from users.serializers.task import AddTaskDependencySerializer, TaskDependencySerializer
from users.services.task_service import TaskService


class AddTaskDependencyAPIView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request, task_id):
        serializer = AddTaskDependencySerializer(
            data=request.data,
        )
        serializer.is_valid(raise_exception=True)

        task = get_object_or_404(
            Task.objects.select_related(
                "project",
                "project__workspace",
            ),
            id=task_id,
            is_deleted=False,
        )

        predecessor = serializer.validated_data["predecessor"]

        dependency = TaskService.add_dependency(
            task=task,
            predecessor=predecessor,
            user=request.user,
            dependency_type=serializer.validated_data.get(
                "dependency_type",
                "BLOCKS",
            ),
        )

        response_serializer = TaskDependencySerializer(
            dependency,
        )

        return Response(
            {
                "success": True,
                "code": "DEPENDENCY_CREATED",
                "message": (
                    "Task dependency created successfully."
                ),
                "data": response_serializer.data,
                "errors": None,
            },
            status=status.HTTP_201_CREATED,
        )


class RemoveTaskDependencyAPIView(APIView):
    permission_classes = [IsAuthenticated]

    def delete(
        self,
        request,
        task_id,
        predecessor_id,
    ):
        task = get_object_or_404(
            Task.objects.select_related(
                "project",
                "project__workspace",
            ),
            id=task_id,
            is_deleted=False,
        )

        predecessor = get_object_or_404(
            Task,
            id=predecessor_id,
        )

        TaskService.remove_dependency(
            task=task,
            predecessor=predecessor,
            user=request.user,
        )

        return Response(
            {
                "success": True,
                "code": "DEPENDENCY_REMOVED",
                "message": (
                    "Task dependency removed successfully."
                ),
                "data": {
                    "task_id": task.id,
                    "predecessor_id": predecessor.id,
                },
                "errors": None,
            },
            status=status.HTTP_200_OK,
        )