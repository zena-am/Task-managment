from rest_framework import viewsets, permissions
from django.contrib.auth import get_user_model
from users.errors.exceptions import TaskAlreadyAssigned
from users.serializers import TaskCreateUpdateSerializer,TaskSerializer,ManagerReportReviewSerializer
from users.serializers.task import ProjectWithoutManagerSerializer, TechnicalReportDetailSerializer
from users.services.task_query_service import ProjectTaskCart, TaskCart, TaskQueryService
from users.services.task_service import TaskService
from users.services.task_transfer_service import ProjectService, RoleService, TaskTransferService
from ..models import ProjectRole,Project, TechnicalReportForm
from users.models import Task
from rest_framework.decorators import action
from ..permissions import CanUpdateTaskStatus, IsTeamManager, IsTeamManagerForProject, TaskPermission
from drf_spectacular.utils import extend_schema,OpenApiExample, OpenApiTypes
from django.db.models import Q,F,Sum,Count
from rest_framework import viewsets, permissions, status
from rest_framework.response import Response
from ..models import ProjectRole,Project, User
from rest_framework.views import APIView
from rest_framework.permissions import IsAuthenticated
from django.shortcuts import get_object_or_404
from django.utils import timezone
from datetime import timedelta, datetime
from drf_spectacular.utils import extend_schema, extend_schema_view, OpenApiParameter
from drf_spectacular.types import OpenApiTypes
from rest_framework.exceptions import ValidationError
from rest_framework import serializers
from rest_framework.parsers import MultiPartParser, FormParser

User = get_user_model()

@extend_schema_view(
    list=extend_schema(
        tags=['المهام'],
        summary="فلترة المهمات الشخصية",
        description="يعيد هذا الرابط  كل المهام المرتبطة بالمستخدم الحالي (كموظف لديه مهام)، مع دعم الفلترة  الداخلية",
        parameters=[
            OpenApiParameter(
                name='priority', type=OpenApiTypes.STR, location=OpenApiParameter.QUERY,
                description="الفلترة بحسب الأولوية", enum=['low', 'medium', 'high']
            ),
            OpenApiParameter(
                name='deadline', type=OpenApiTypes.STR, location=OpenApiParameter.QUERY,
                description="الفلترة بحسب تاريخ التسليم التراكمي", enum=['today', 'tomorrow', 'week', 'month']
            ),
        ]
    ),
    retrieve=extend_schema(
        tags=['المهام'],
        summary="جلب تفاصيل مهمة محددة",
        description="يعيد تفاصيل مهمة واحدة كاملة بالأسماء والصور بناءً على الـ ID الممرر في الرابط."
    ),
    create=extend_schema(
        tags=['المهام'],
        summary="إنشاء مهمة جديدة داخل المشروع(للمدير)",
        description=("يسمح لمدراء المشاريع بإنشاء مهمة وإسنادها لموظف محدد داخل المشروع."),
        request=TaskCreateUpdateSerializer,
        responses={201: TaskSerializer},

    ),

    partial_update=extend_schema(

        tags=['المهام'],
        summary="تعديل كامل للمهمة (خاص بالمدراء والمشرفين فقط)",
        description=( "يسمح للمشرفين أو مدراء المشاريع بتعديل أي حقل من حقول مهمة معينة بحرية"),
        request=TaskCreateUpdateSerializer,
        responses={201: TaskSerializer},

    ),


    destroy=extend_schema(
        tags=['المهام'],
        summary="حذف مهمة نهائياً (للمدير)",
        description=( "يسمح بحذف سجل المهمة تماماً من قاعدة البيانات باستخدام الـ ID."),
        request=TaskCreateUpdateSerializer,
        responses={201: TaskSerializer},

    ),

)
class TaskView(viewsets.ModelViewSet):
    User = get_user_model()
    parser_classes = (MultiPartParser, FormParser)
    permission_classes = [IsAuthenticated, TaskPermission]

    def get_serializer_class(self):
        if self.action in ['create', 'update', 'partial_update']:
            return TaskCreateUpdateSerializer

        return TaskSerializer

    def get_queryset(self):
        user = self.request.user
        return TaskQueryService.get_user_tasks(user, self.request.query_params)
    def list(self, request, *args, **kwargs):
        return super().list(request, *args, **kwargs)

    def retrieve(self, request, *args, **kwargs):
        return super().retrieve(request, *args, **kwargs)

    def perform_create(self, serializer):
        TaskService.create_task(self.request.user, serializer)

    def perform_update(self, serializer):
        instance = self.get_object()
        status_value = self.request.data.get("status")
        TaskService.perform_update(serializer, instance, self.request.user,status_value)

    @extend_schema(
        tags=['المهام'],
        summary="جلب إحصائيات ____ كروت الصفحة_____ الرئيسية للمستخدم",
        description="يعيد هذا الرابط أعداد المهام الخاصة بالمستخدم الحالي مقسمة إلى ثلاثة أعداد: المهام بانتظار البدء، المهام قيد التنفيذ، والمهام المكتملة لتغذية كروت الواجهة الرئيسية."
        "                        يتم جلب عدد للحالات التي لدي                          ",
        responses={
        200: {
            "type": "object",
            "properties": {
                "todo_tasks_count": {"type": "integer"},
                "in_progress_tasks_count": {"type": "integer"},
                "completed_tasks_count": {"type": "integer"}
            }
        }
    }
    )
    @action(detail=False, methods=['get'], url_path='card')
    def getCard(self, request):
        data = TaskCart.get_user_card_stats(request.user)
        return Response(data)

    @extend_schema(
        tags=['واجهات المشاريع'],
        summary="جلب إحصائيات ____ كروت الصفحة_____  لمشروع محدد",
        description="يمكن للمستخدم ان يستعرض مهامه الشخصية اذا كان موظف ومهام الفريق ومهامه اذا كان مدير ",
        responses={
    200: {
        "type": "object",
        "properties": {
            "project_total_tasks": {
                "type": "object",
                "properties": {
                    "todo": {"type": "integer"},
                    "in_progress": {"type": "integer"},
                    "completed": {"type": "integer"}
                }
            },
            "my_tasks": {
                "type": "object",
                "properties": {
                    "todo": {"type": "integer"},
                    "in_progress": {"type": "integer"},
                    "completed": {"type": "integer"}
                }
            },
            "team_tasks": {
                "type": "object",
                "properties": {
                    "todo": {"type": "integer"},
                    "in_progress": {"type": "integer"},
                    "completed": {"type": "integer"}
                }
            }
        }
    }
}
    )
    @action(detail=True, methods=['get'], url_path='Projectcard')
    def get_project_card(self, request, pk=None):
        project = self.get_object()
        data = ProjectTaskCart.get_project_card_stats(request.user, project)
        return Response(data)

    @extend_schema(
        tags=['المهام'],
        summary="جلب قائمة المهام الخاصة بالمستخدم",
        description="يعيد هذا الرابط جميع المهام التي تم إسنادها للمستخدم الحالي  مع تفاصيل الموظفين الكاملة ",
    )
    @action(detail=False, methods=['get'], url_path='user')
    def userTask(self, request):
        user = request.user
        queryset = Task.objects.filter(assigned_to=user).distinct()
        serializer = self.get_serializer(queryset, many=True)
        return Response(serializer.data)

    @extend_schema(
        tags=['المهام'],
        summary="جلب المهام التي يشرف عليها المدير حالياً (لمدير الفريق)",
        description="يعيد هذا الرابط المهام التي يكون المستخدم مشرفاً عليها ليتابع أداء فريق العمل ",
    )
    @action(detail=False, methods=['get'], url_path='supervised',permission_classes=[ IsAuthenticated,IsTeamManager ])
    def supervised(self, request):
        user = request.user
        data = TaskQueryService.get_user_card_stats(request.user)
        return Response(data)




        queryset = Task.objects.filter(supervisor=user).distinct()
        queryset = self.filter_by_priority(queryset)
        queryset = self.filter_by_deadline(queryset)
        serializer = self.get_serializer(queryset, many=True)



    def partial_update(self, request, *args, **kwargs):
        return super().partial_update(request, *args, **kwargs)

"""
        target_end_time = deadline_map.get(deadline_param.lower())
        if target_end_time:
            if deadline_param.lower() == 'tomorrow':
                    tomorrow_start = today_start + timedelta(days=1)
                    return queryset.filter(end_time__gte=tomorrow_start, end_time__lt=target_end_time)

            return queryset.filter(end_time__gte=today_start, end_time__lte=target_end_time)
"""

#######################################################################################################
class ReviewTechnicalReportAPIView(APIView):

    permission_classes = [
        IsAuthenticated,
        TaskPermission
    ]

    @extend_schema(
        tags=["التقارير التقنية"],
        summary="قبول او رفض التقرير التقني للمهمة",
            description=(
        "تمكن المدير أو المشرف من مراجعة التقرير التقني المرتبط بالمهمة "
        "يمكن للمدير تغيير حالة التقرير إلى 'APPROVED' أو 'REJECTED'، "
        "وإضافة ملاحظات (feedback_text) التي تُسجَّل ضمن manager_feedbacks. "
        "'DONE' حال الموافقة، تتحول حالة المهمة إلى  "
        "في حال الرفض، تبقى المهمة في ويجب على الموظف تعديل التقرير."
        "كما يمكن للمدير التعديل بعد الارسال"
    ),
        request=ManagerReportReviewSerializer,
        responses={200: OpenApiTypes.OBJECT}
    )
    def patch(self, request, task_id):

        task = get_object_or_404(Task, id=task_id)

        self.check_object_permissions(request, task)

        report = task.technical_reports.order_by(
            '-created_at'
        ).first()

        if not report:
            return Response(
                {
                    "error": "No technical report found for this task."
                },
                status=status.HTTP_400_BAD_REQUEST
            )

        serializer = ManagerReportReviewSerializer(
            instance=report,
            data=request.data,
            context={'request': request}
        )

        serializer.is_valid(raise_exception=True)

        response_data = TaskService.review_technical_report(
            task=task,
            report=report,
            manager_user=request.user,
            feedback_text=serializer.validated_data.get('feedback_text'),
            new_status=serializer.validated_data.get('status'),
            quality=serializer.validated_data.get('quality')
        )

        return Response(
            response_data,
            status=status.HTTP_200_OK
        )


#######################################################################################################
class ClaimTaskAPIView(APIView):

    permission_classes = [IsAuthenticated]

    @extend_schema(
        tags=['المهام'],
        summary="استلام مهمة متاحة",
        description="يسمح للموظف باستلام مهمة غير مسندة ليصبح المسؤول عنها",
        request=None,
        responses={200: OpenApiTypes.OBJECT}
    )
    def patch(self, request, task_id):

        task = get_object_or_404(
            Task,
            id=task_id
        )

        TaskService.claim_task(
            task,
            request.user
        )

        return Response(
            {
                "message":
                f"You have successfully claimed the task: '{task.title}'."
            },
            status=status.HTTP_200_OK
        )
#######################################################################################################
@extend_schema(
        tags=['المهام'],
        summary="تحديث حالة المهمة فقط",
        description="يسمح للموظف بتحديث حقل الحالة  الخاص بالمهمة فقط ويشترط أن تكون القيمة إما"
        " 'TODO' أو 'INPROGRESS' أو 'DONE' ",
        request=None,
        responses={200: OpenApiTypes.OBJECT}
    )
class TaskStatusUpdateAPIView(APIView):
    permission_classes = [IsAuthenticated, CanUpdateTaskStatus]

    def patch(self, request, task_id):
        task = get_object_or_404(Task, id=task_id)

        self.check_object_permissions(request, task)

        status_value = request.data.get("status")
        if not status_value:
            return Response({"error": "Status value is required."}, status=400)

        TaskService.update_status(task, request.user, status_value)

        return Response(
            {"message": f"Task status updated successfully to {status_value}."},
            status=status.HTTP_200_OK
        )
#######################################################################################################
@extend_schema(
    tags=['التقارير الخاصة بالموظف']
)
class TechnicalReportDetailView(APIView):
    permission_classes = [IsAuthenticated,TaskPermission]
    @extend_schema(
        summary="عرض التقارير",
    )
    def get(self, request, task_id, format=None):
        task = get_object_or_404(Task, id=task_id)
        self.check_object_permissions(request, task)
        report = TechnicalReportForm.objects.filter(task_id=task_id).order_by('-created_at').first()
        if not report:
            return Response({"detail": "Report not found."}, status=404)
        serializer = TechnicalReportDetailSerializer(report)
        return Response(serializer.data)

#######################################################################################################
class AssignManagerSerializer(serializers.Serializer):
    user_id = serializers.IntegerField()
    role = serializers.CharField(required=True)
@extend_schema(
    tags=["عرض ونقل المشاريع التي بدون مشرف"],
        summary="تعيين مشرف جديد",
)
class TransferSystemBot(APIView):
    permission_classes = [IsAuthenticated,IsTeamManagerForProject]

    @extend_schema(
        summary="عرض  المشاريع التي بدون مدير ",
        request=None,
        responses={
        200: ProjectWithoutManagerSerializer
    }
    )
    def get(self, request):
        projects = ProjectService.get_projects_without_manager()

        serializer = ProjectWithoutManagerSerializer(projects,many=True
        )

        return Response(serializer.data)



    @extend_schema(
        request=AssignManagerSerializer,
        summary="تعيين الدور جديد للموظفين "
    )
    def post(self, request, project_id):

        project = get_object_or_404(
            Project,
            id=project_id
        )

        serializer = AssignManagerSerializer(
            data=request.data
        )

        serializer.is_valid(raise_exception=True)

        target_user = get_object_or_404(
            User,
            id=serializer.validated_data["user_id"],
        )

        RoleService.set_user_role(
            project=project,
            user=target_user,
            performed_by=request.user,
            new_role="MANAGER",
        )

        return Response(
            {"message": "Manager assigned successfully."}
        )




#######################################################################################################
from rest_framework import serializers

class AssignSingleTaskSerializer(serializers.Serializer):
    assigned_to = serializers.IntegerField(required=True)

@extend_schema(
    tags=['نقل المهمة لموظف جديد'],
    summary="تعيين موظف بدور جديد",
)
class TransferTaskToUser(APIView):
    permission_classes = [IsAuthenticated, IsTeamManagerForProject]

    @extend_schema(
        request=AssignSingleTaskSerializer,
        responses={
            200: {
                "type": "object",
                "properties": {
                    "message": {"type": "string"},
                    "assigned_to": {"type": "string"}
                }
            }
        },
        summary="تعيين موظف جديد للمهام غير المسندة",

    )
    def patch(self, request, task_id, project_id):
            project = get_object_or_404(Project, id=project_id)
            task = get_object_or_404(Task, id=task_id, project=project)

            self.check_object_permissions(request, task)

            serializer = AssignSingleTaskSerializer(data=request.data)
            serializer.is_valid(raise_exception=True)

            new_assignee = get_object_or_404(User, id=serializer.validated_data['assigned_to'])

            TaskService.assign_task_to_user(
                task=task,
                new_assignee=new_assignee,
                performed_by=request.user,
                project=project
            )

            return Response({"message": "تم إسناد المهمة للمستخدم بنجاح"})

    @extend_schema(
        summary="استعراض المهام المعلقة بدون موظف",
        description="تعيد قائمة المهام غير المسندة في المشروع",
        request=None,
        responses={
        200: TaskSerializer
    }
    )
    def get(self, request, project_id):
        project = get_object_or_404(Project, id=project_id)
        self.check_object_permissions(request, project)

        tasks = TaskTransferService.get_orphaned_tasks(project)
        serializer = TaskSerializer(tasks, many=True)
        return Response(serializer.data)