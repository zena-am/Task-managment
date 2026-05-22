from rest_framework import viewsets, permissions
from django.contrib.auth import get_user_model
from users.serializers import TaskCreateUpdateSerializer,TaskSerializer,ManagerReportReviewSerializer
from users.serializers.task import TechnicalReportDetailSerializer
from users.services.task_query_service import TaskQueryService
from users.services.task_service import TaskService
from users.services.task_transfer_service import TaskTransferService
from ..models import ProjectRole,Project, TechnicalReportForm
from users.models import Task
from rest_framework.decorators import action
from ..permissions import IsProjectManagerOrReadOnly
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
        description="يسمح لمدراء المشاريع بإنشاء مهمة وإسنادها لموظف محدد داخل المشروع."
    ),
    partial_update=extend_schema(

        tags=['المهام'],
        summary="تعديل كامل للمهمة (خاص بالمدراء والمشرفين فقط)",
        description="يسمح للمشرفين أو مدراء المشاريع بتعديل أي حقل من حقول مهمة معينة بحرية",
    ),

    destroy=extend_schema(
        tags=['المهام'],
        summary="حذف مهمة نهائياً (للمدير)",
        description="يسمح بحذف سجل المهمة تماماً من قاعدة البيانات باستخدام الـ ID."
    ),


)
class TaskView(viewsets.ModelViewSet):
    User = get_user_model()
    permission_classes = [IsAuthenticated, IsProjectManagerOrReadOnly]
    def get_serializer_class(self):
        if self.action in ['create', 'update', 'partial_update']:
            return TaskCreateUpdateSerializer

        return TaskSerializer




    def get_queryset(self):
        user = self.request.user

        return TaskQueryService.get_user_tasks(user, self.request.query_params)

    @extend_schema(
        tags=['المهام'],
        summary="جلب إحصائيات ____ كروت الصفحة_____ الرئيسية للمستخدم",
        description="يعيد هذا الرابط أعداد المهام الخاصة بالمستخدم الحالي مقسمة إلى ثلاثة أعداد: المهام بانتظار البدء، المهام قيد التنفيذ، والمهام المكتملة لتغذية كروت الواجهة الرئيسية."
        "                        يتم جلب عدد للحالات التي لدي                          "
    )
    @action(detail=False, methods=['get'], url_path='card')
    def getCard(self, request):
        data = TaskQueryService.get_user_card_stats(request.user)
        return Response(data)


    def list(self, request, *args, **kwargs):
        return super().list(request, *args, **kwargs)

    def retrieve(self, request, *args, **kwargs):
        return super().retrieve(request, *args, **kwargs)

    def perform_create(self, serializer):
        TaskService.create_task(serializer, self.request.user)

    def perform_update(self, serializer):
        instance = self.get_object()
        status_value = self.request.data.get("status")
        TaskService.perform_update(serializer, instance, self.request.user,status_value)

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
        summary="جلب المهام التي يشرف عليها المستخدم حالياً (  لمدير الفريق)",
        description="يعيد هذا الرابط المهام التي يكون المستخدم مشرفاً عليها ليتابع أداء فريق العمل ",
    )
    @action(detail=False, methods=['get'], url_path='supervised')
    def supervised(self, request):
        user = request.user
        queryset = Task.objects.filter(supervisor=user).distinct()
        queryset = self.filter_by_priority(queryset)
        queryset = self.filter_by_deadline(queryset)
        serializer = self.get_serializer(queryset, many=True)
        return Response(serializer.data)




    @extend_schema(
        tags=['المهام'],
        summary="  (للمدير) تعيين المهمة ",
        description="يسمح هذا الرابط للموظف العادي باستلام مهمة متاحة ليس لها منفذ بعد، ليصبح هو المسؤول عنه",
        request=None,
        responses={200: OpenApiTypes.OBJECT}
    )
    @action(detail=True, methods=['patch'], url_path='claim')
    def claim(self, request, pk=None):
        task = get_object_or_404(Task, pk=pk)

        TaskService.claim_task(task, request.user)

        return Response(
            {"message": f"You have successfully claimed the task: '{task.title}'."},
            status=status.HTTP_200_OK
        )





    @extend_schema(
        tags=['المهام'],
        summary="تحديث حالة المهمة فقط",
        description="يسمح للموظف بتحديث حقل الحالة  الخاص بالمهمة فقط ويشترط أن تكون القيمة إما"
        " 'TODO' أو 'INPROGRESS' أو 'DONE' ",
        request=None,
        responses={200: OpenApiTypes.OBJECT}
    )
    @action(detail=True, methods=['patch'], url_path='status_update', permission_classes=[IsAuthenticated])
    def status_update(self, request, *args, **kwargs):
        task = self.get_object()
        status_value = request.data.get("status")
        if not status_value:
            return Response({"error": "Status value is required."}, status=400)
        TaskService.update_status(task, request.user, status_value)
        return Response(
            {"message": f"Task status updated successfully to {status_value}."},
            status=status.HTTP_200_OK
        )



    @extend_schema(
    tags=['لوحة المدير'],
    summary="مراجعة التقرير التقني للمهمة",
    description=(
        "تمكن المدير أو المشرف من مراجعة التقرير التقني المرتبط بالمهمة "
        "يمكن للمدير تغيير حالة التقرير إلى 'APPROVED' أو 'REJECTED'، "
        "وإضافة ملاحظات (feedback_text) التي تُسجَّل ضمن manager_feedbacks. "
        "'DONE' حال الموافقة، تتحول حالة المهمة إلى  "
        "في حال الرفض، تبقى المهمة في ويجب على الموظف تعديل التقرير."
        "كما يمكن للمدير التعديل بعد الارسال"
    ),
    request=ManagerReportReviewSerializer,
    responses={200: OpenApiTypes.OBJECT})
    @action(detail=True, methods=['patch'], url_path='review_report')
    def review_report(self, request, pk=None):
        task = get_object_or_404(Task, pk=pk)
        if not report:
            return Response({"error": "No technical report found for this task."}, status=400)
        report = task.technical_reports.order_by('-created_at').first()
        serializer = ManagerReportReviewSerializer(data=request.data, instance=report, context={'request': request})
        serializer.is_valid(raise_exception=True)

        response_data = TaskService.review_technical_report(
            task=task,
            report=report,
            manager_user=request.user,
            feedback_text=serializer.validated_data.get('feedback_text'),
            new_status=serializer.validated_data.get('status')
        )
        return Response(response_data, status=status.HTTP_200_OK)



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
@extend_schema(
    tags=['التقارير الخاصة بالموظف']
)
class TechnicalReportDetailView(APIView):
    permission_classes = [IsAuthenticated]
    @extend_schema(
        summary="عرض التقارير",
    )
    def get(self, request, task_id, format=None):
        report = TechnicalReportForm.objects.filter(task_id=task_id).order_by('-created_at').first()
        if not report:
            return Response({"detail": "Report not found."}, status=404)
        serializer = TechnicalReportDetailSerializer(report)
        return Response(serializer.data)


@extend_schema(
    tags=['نقل المشروع لمشرف جديد'],
        summary="تعيين مشرف جديد",
)
class TransferSystemBot(APIView):
    permission_classes = [IsAuthenticated, IsProjectManagerOrReadOnly]


    @extend_schema(
        summary="استعراض المهام المعلقة تحت إشراف النظام",
        description="تعيد هذه الدالة قائمة بجميع المهام التابعة للمشروع والتي لا تمتلك مديراً حالياً وتوجد تحت إدارة البوت الافتراضي."
    )
    def get(self, request, project_id):
        project = get_object_or_404(Project, id=project_id)
        self.check_object_permissions(request, project)

        tasks = TaskTransferService.get_orphaned_tasks(project)

        serializer = TaskSerializer(tasks, many=True)
        return Response(serializer.data)




    @extend_schema(
        summary="تعيين مشرف جديد للمهام المعلقة",
        description="يقوم الأدمن بتعيين مشرف بديل  يختار من موظفين الفضاء او يرسل دعوة لموظف خارج الفضاء ليتولى المهام بدلا من المدير المغادر"
        "{\n"
            "    \"new_supervisor_id\": 5\n"
            "}\n"

    )
    def post(self, request, project_id):
        project = get_object_or_404(Project, id=project_id)
        self.check_object_permissions(request, project)

        new_supervisor_id = request.data.get("new_supervisor_id")
        if not new_supervisor_id:
            return Response(
                {"error": "New supervisor ID is required."},
                status=400
            )

        new_supervisor = get_object_or_404(User, id=new_supervisor_id)

        count = TaskTransferService.transfer_tasks(project, new_supervisor)

        if count == 0:
            return Response(
                {"message": "No orphaned tasks found."},
                status=200
            )

        return Response({
            "message": f"Successfully transferred {count} tasks."
        })