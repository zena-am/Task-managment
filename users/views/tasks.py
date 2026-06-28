from django.contrib.auth import get_user_model
from django.shortcuts import get_object_or_404
from drf_spectacular.types import OpenApiTypes
from drf_spectacular.utils import extend_schema, extend_schema_view, OpenApiParameter
from rest_framework import serializers, status, viewsets
from rest_framework.decorators import action
from rest_framework.parsers import FormParser, MultiPartParser
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from users.errors.exceptions import BaseAppException, PermissionDeniedError
from users.errors.messages.success import success_response
from users.models import Project, ProjectRole, Task, TechnicalReportForm
from users.permissions import CanUpdateTaskStatus, IsTeamManager, IsTeamManagerForProject, TaskPermission
from users.serializers import TaskCreateUpdateSerializer, TaskSerializer, ManagerReportReviewSerializer
from users.serializers.task import ProjectWithoutManagerSerializer, TechnicalReportDetailSerializer
from users.services.task_query_service import ProjectTaskCart, TaskCart, TaskQueryService
from users.services.task_service import TaskService
from users.services.task_transfer_service import ProjectService, RoleService, TaskTransferService

User = get_user_model()


@extend_schema_view(
    list=extend_schema(
        tags=['المهام'],
        summary="فلترة المهمات الشخصية",
        parameters=[
            OpenApiParameter(name='status', type=OpenApiTypes.STR, location=OpenApiParameter.QUERY),
            OpenApiParameter(name='priority', type=OpenApiTypes.STR, location=OpenApiParameter.QUERY),
            OpenApiParameter(name='deadline', type=OpenApiTypes.STR, location=OpenApiParameter.QUERY),
        ],
    ),
    retrieve=extend_schema(tags=['المهام'], summary="جلب تفاصيل مهمة محددة"),
    create=extend_schema(tags=['المهام'], summary="إنشاء مهمة جديدة داخل المشروع", request=TaskCreateUpdateSerializer, responses={201: TaskSerializer}),
    partial_update=extend_schema(tags=['المهام'], summary="تعديل جزئي للمهمة", request=TaskCreateUpdateSerializer, responses={200: TaskSerializer}),
    destroy=extend_schema(tags=['المهام'], summary="حذف مهمة نهائياً"),
)
class TaskView(viewsets.ModelViewSet):
    parser_classes = (MultiPartParser, FormParser)
    permission_classes = [IsAuthenticated, TaskPermission]

    def get_serializer_class(self):
        if self.action in ['create', 'update', 'partial_update']:
            return TaskCreateUpdateSerializer
        return TaskSerializer

    def get_queryset(self):
        return TaskQueryService.get_user_tasks(self.request.user, self.request.query_params)

    def list(self, request, *args, **kwargs):
        queryset = self.filter_queryset(self.get_queryset())
        page = self.paginate_queryset(queryset)
        if page is not None:
            serializer = TaskSerializer(page, many=True, context=self.get_serializer_context())
            paginated = self.paginator.get_paginated_response(serializer.data)
            return Response(success_response(
                message="Tasks retrieved successfully",
                code="TASKS_RETRIEVED",
                data=paginated.data,
            ), status=status.HTTP_200_OK)

        serializer = TaskSerializer(queryset, many=True, context=self.get_serializer_context())
        return Response(success_response(
            message="Tasks retrieved successfully",
            code="TASKS_RETRIEVED",
            data=serializer.data,
        ), status=status.HTTP_200_OK)

    def retrieve(self, request, *args, **kwargs):
        task = self.get_object()
        serializer = TaskSerializer(task, context=self.get_serializer_context())
        return Response(success_response(
            message="Task retrieved successfully",
            code="TASK_RETRIEVED",
            data=serializer.data,
        ), status=status.HTTP_200_OK)

    def create(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        task = TaskService.create_task(request.user, serializer)
        response_serializer = TaskSerializer(task, context=self.get_serializer_context())
        return Response(success_response(
            message="Task created successfully",
            code="TASK_CREATED",
            data=response_serializer.data,
        ), status=status.HTTP_201_CREATED)

    def update(self, request, *args, **kwargs):
        partial = kwargs.pop('partial', False)
        instance = self.get_object()
        serializer = self.get_serializer(instance, data=request.data, partial=partial)
        serializer.is_valid(raise_exception=True)
        status_value = request.data.get("status")
        TaskService.perform_update(serializer, instance, request.user, status_value)
        response_serializer = TaskSerializer(instance, context=self.get_serializer_context())
        return Response(success_response(
            message="Task updated successfully",
            code="TASK_UPDATED",
            data=response_serializer.data,
        ), status=status.HTTP_200_OK)

    def partial_update(self, request, *args, **kwargs):
        kwargs['partial'] = True
        return self.update(request, *args, **kwargs)

    def destroy(self, request, *args, **kwargs):
        task = self.get_object()
        task_id = task.id
        self.perform_destroy(task)
        return Response(success_response(
            message="Task deleted successfully",
            code="TASK_DELETED",
            data={"task_id": task_id},
        ), status=status.HTTP_200_OK)

    @extend_schema(tags=['المهام'], summary="جلب إحصائيات كروت الصفحة الرئيسية للمستخدم")
    @action(detail=False, methods=['get'], url_path='card')
    def getCard(self, request):
        data = TaskCart.get_user_card_stats(request.user)
        return Response(success_response(
            message="Task cards retrieved successfully",
            code="TASK_CARDS_RETRIEVED",
            data=data,
        ), status=status.HTTP_200_OK)

    @extend_schema(tags=['واجهات المشاريع'], summary="جلب إحصائيات كروت مشروع محدد")
    @action(detail=True, methods=['get'], url_path='Projectcard')
    def get_project_card(self, request, pk=None):
        project = get_object_or_404(Project, id=pk)
        data = ProjectTaskCart.get_project_card_stats(request.user, project)
        return Response(success_response(
            message="Project task cards retrieved successfully",
            code="PROJECT_TASK_CARDS_RETRIEVED",
            data=data,
        ), status=status.HTTP_200_OK)

    @extend_schema(tags=['المهام'], summary="جلب قائمة المهام الخاصة بالمستخدم")
    @action(detail=False, methods=['get'], url_path='user')
    def userTask(self, request):
        queryset = Task.objects.filter(assigned_to=request.user).distinct()
        serializer = TaskSerializer(queryset, many=True, context=self.get_serializer_context())
        return Response(success_response(
            message="User tasks retrieved successfully",
            code="USER_TASKS_RETRIEVED",
            data=serializer.data,
        ), status=status.HTTP_200_OK)

    @extend_schema(tags=['المهام'], summary="جلب المهام التي يديرها المدير حالياً")
    @action(detail=False, methods=['get'], url_path='supervised', permission_classes=[IsAuthenticated, IsTeamManager])
    def supervised(self, request):
        managed_project_ids = ProjectRole.objects.filter(
            user=request.user,
            role__in=['ADMIN', 'MANAGER'],
        ).values_list('project_id', flat=True)
        queryset = Task.objects.filter(project_id__in=managed_project_ids).distinct()
        serializer = TaskSerializer(queryset, many=True, context=self.get_serializer_context())
        return Response(success_response(
            message="Managed tasks retrieved successfully",
            code="MANAGED_TASKS_RETRIEVED",
            data=serializer.data,
        ), status=status.HTTP_200_OK)


class ReviewTechnicalReportAPIView(APIView):
    permission_classes = [IsAuthenticated]

    @extend_schema(
        tags=["التقارير التقنية"],
        summary="قبول أو رفض التقرير التقني للمهمة",
        request=ManagerReportReviewSerializer,
        responses={200: OpenApiTypes.OBJECT},
    )
    def patch(self, request, task_id):
        task = get_object_or_404(Task, id=task_id)
        if not ProjectRole.objects.filter(project=task.project, user=request.user, role__in=['ADMIN', 'MANAGER']).exists():
            raise PermissionDeniedError()

        report = task.technical_reports.order_by('-created_at').first()
        if not report:
            raise BaseAppException(
                detail="No technical report found for this task.",
                code="TECHNICAL_REPORT_NOT_FOUND",
                status_code=400,
            )

        serializer = ManagerReportReviewSerializer(instance=report, data=request.data, context={'request': request})
        serializer.is_valid(raise_exception=True)

        response_data = TaskService.review_technical_report(
            task=task,
            report=report,
            manager_user=request.user,
            feedback_text=serializer.validated_data.get('feedback_text'),
            new_status=serializer.validated_data.get('status'),
            quality=serializer.validated_data.get('quality'),
        )

        return Response(success_response(
            message="Technical report reviewed successfully",
            code="TECHNICAL_REPORT_REVIEWED",
            data=response_data,
        ), status=status.HTTP_200_OK)


class ClaimTaskAPIView(APIView):
    permission_classes = [IsAuthenticated]

    @extend_schema(tags=['المهام'], summary="استلام مهمة متاحة", request=None, responses={200: OpenApiTypes.OBJECT})
    def patch(self, request, task_id):
        task = get_object_or_404(Task, id=task_id)
        TaskService.claim_task(task, request.user)

        return Response(success_response(
            message="Task claimed successfully",
            code="TASK_CLAIMED",
            data={"task_id": task.id},
        ), status=status.HTTP_200_OK)


@extend_schema(tags=['المهام'], summary="تحديث حالة المهمة فقط", request=None, responses={200: OpenApiTypes.OBJECT})
class TaskStatusUpdateAPIView(APIView):
    permission_classes = [IsAuthenticated, CanUpdateTaskStatus]

    def patch(self, request, task_id):
        task = get_object_or_404(Task, id=task_id)
        self.check_object_permissions(request, task)

        status_value = request.data.get("status")
        if not status_value:
            raise BaseAppException(
                detail="Status value is required.",
                code="STATUS_REQUIRED",
                status_code=400,
            )

        task = TaskService.update_status(task, request.user, status_value)
        return Response(success_response(
            message="Task status updated successfully",
            code="TASK_STATUS_UPDATED",
            data={"task_id": task.id, "status": task.status},
        ), status=status.HTTP_200_OK)


@extend_schema(tags=['التقارير الخاصة بالموظف'])
class TechnicalReportDetailView(APIView):
    permission_classes = [IsAuthenticated, TaskPermission]

    @extend_schema(summary="عرض آخر تقرير لمهمة")
    def get(self, request, task_id, format=None):
        task = get_object_or_404(Task, id=task_id)
        self.check_object_permissions(request, task)
        report = TechnicalReportForm.objects.filter(task_id=task_id).order_by('-created_at').first()
        if not report:
            raise BaseAppException(
                detail="Report not found.",
                code="REPORT_NOT_FOUND",
                status_code=404,
            )
        serializer = TechnicalReportDetailSerializer(report, context={'request': request})
        return Response(success_response(
            message="Technical report retrieved successfully",
            code="TECHNICAL_REPORT_RETRIEVED",
            data=serializer.data,
        ), status=status.HTTP_200_OK)


class AssignManagerSerializer(serializers.Serializer):
    user_id = serializers.IntegerField()
    role = serializers.ChoiceField(choices=['ADMIN', 'MANAGER', 'EMPLOYEE'], required=False, default='MANAGER')


@extend_schema(tags=["عرض ونقل المشاريع التي بدون مشرف"], summary="تعيين مشرف جديد")
class TransferSystemBot(APIView):
    permission_classes = [IsAuthenticated]

    @extend_schema(summary="عرض المشاريع التي بدون مدير", request=None, responses={200: ProjectWithoutManagerSerializer})
    def get(self, request):
        projects = ProjectService.get_projects_without_manager()
        serializer = ProjectWithoutManagerSerializer(projects, many=True, context={'request': request})
        return Response(success_response(
            message="Projects without manager retrieved successfully",
            code="PROJECTS_WITHOUT_MANAGER_RETRIEVED",
            data=serializer.data,
        ), status=status.HTTP_200_OK)

    @extend_schema(request=AssignManagerSerializer, summary="تعيين الدور الجديد للموظف")
    def post(self, request, project_id):
        project = get_object_or_404(Project, id=project_id)
        if not ProjectRole.objects.filter(project=project, user=request.user, role__in=['ADMIN', 'MANAGER']).exists():
            raise PermissionDeniedError()

        serializer = AssignManagerSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        target_user = get_object_or_404(User, id=serializer.validated_data["user_id"])
        new_role = serializer.validated_data.get("role", "MANAGER")

        RoleService.set_user_role(
            project=project,
            user=target_user,
            performed_by=request.user,
            new_role=new_role,
        )

        return Response(success_response(
            message="Project role updated successfully",
            code="PROJECT_ROLE_UPDATED",
            data={"project_id": project.id, "user_id": target_user.id, "role": new_role},
        ), status=status.HTTP_200_OK)


class AssignSingleTaskSerializer(serializers.Serializer):
    assigned_to = serializers.IntegerField(required=True)


@extend_schema(tags=['نقل المهمة لموظف جديد'], summary="تعيين موظف لمهمة")
class TransferTaskToUser(APIView):
    permission_classes = [IsAuthenticated, IsTeamManagerForProject]

    @extend_schema(request=AssignSingleTaskSerializer, summary="تعيين موظف جديد لمهمة غير مسندة")
    def patch(self, request, project_id, task_id):
        project = get_object_or_404(Project, id=project_id)
        task = get_object_or_404(Task, id=task_id, project=project)
        self.check_object_permissions(request, task)

        serializer = AssignSingleTaskSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        new_assignee = get_object_or_404(User, id=serializer.validated_data['assigned_to'])

        if not ProjectRole.objects.filter(project=project, user=new_assignee).exists():
            raise BaseAppException(
                detail="User is not a member of this project.",
                code="USER_NOT_IN_PROJECT",
                status_code=400,
            )

        TaskTransferService.assign_task_to_user(
            task=task,
            new_assignee=new_assignee,
            performed_by=request.user,
            project=project,
        )

        return Response(success_response(
            message="Task assigned successfully",
            code="TASK_ASSIGNED",
            data={"task_id": task.id, "assigned_to": new_assignee.id},
        ), status=status.HTTP_200_OK)

    @extend_schema(summary="استعراض المهام المعلقة بدون موظف", request=None, responses={200: TaskSerializer})
    def get(self, request, project_id):
        project = get_object_or_404(Project, id=project_id)
        if not ProjectRole.objects.filter(project=project, user=request.user, role__in=['ADMIN', 'MANAGER']).exists():
            raise PermissionDeniedError()

        tasks = TaskTransferService.get_orphaned_tasks(project)
        serializer = TaskSerializer(tasks, many=True, context={'request': request})
        return Response(success_response(
            message="Unassigned tasks retrieved successfully",
            code="UNASSIGNED_TASKS_RETRIEVED",
            data=serializer.data,
        ), status=status.HTTP_200_OK)
