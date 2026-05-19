from jsonschema import ValidationError
from rest_framework import viewsets, permissions
from django.contrib.auth import get_user_model

from users.serializers import TaskCreateUpdateSerializer
from ..models import ProjectRole,Project
from users.models import Task
from rest_framework.decorators import action
from ..permissions import IsProjectManagerOrReadOnly
from ..serializers import TaskSerializer
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
        queryset=Task.objects.filter( Q(assigned_to=user) ).distinct()

        status_param = self.request.query_params.get('status')
        allowed_choices = ['TODO', 'INPROGRESS', 'DONE']

        if status_param:
            if status_param not in allowed_choices:
                raise ValidationError(
                    {"error": f"The provided status is invalid. Allowed choices are: {allowed_choices}"}
                )
            queryset = queryset.filter(status=status_param)

        queryset = self.filter_by_priority(queryset)
        queryset = self.filter_by_deadline(queryset)

        return queryset.order_by('-id')

    @extend_schema(
        tags=['المهام'],
        summary="جلب إحصائيات ____ كروت الصفحة_____ الرئيسية للمستخدم",
        description="يعيد هذا الرابط أعداد المهام الخاصة بالمستخدم الحالي مقسمة إلى ثلاثة أعداد: المهام بانتظار البدء، المهام قيد التنفيذ، والمهام المكتملة لتغذية كروت الواجهة الرئيسية."
        "                        يتم جلب عدد للحالات التي لدي                          "
    )
    @action(detail=False, methods=['get'], url_path='card')
    def getCard(self, request):
        user = request.user

        stats = Task.objects.filter(assigned_to=user).aggregate(
            todo_count=Count('id', filter=Q(status='TODO')),
            in_progress_count=Count('id', filter=Q(status='INPROGRESS')),
            completed_count=Count('id', filter=Q(status='DONE'))
        )
        return Response({
                    "todo_tasks_count": stats['todo_count'] or 0,
                    "in_progress_tasks_count": stats['in_progress_count'] or 0,
                    "completed_tasks_count": stats['completed_count'] or 0
                })


    def filter_by_priority(self, queryset):
        priority_param = self.request.query_params.get('priority')
        if priority_param:
            priority_map = {'low': 'L', 'medium': 'M', 'high': 'H'}
            mapped_priority = priority_map.get(priority_param.lower())

            if not mapped_priority:
                raise ValidationError(
                    {"error": f"The provided priority is invalid. Allowed choices are: {list(priority_map.keys())}"}
                )
            if mapped_priority:
                return queryset.filter(priority=mapped_priority)
        return queryset

    def filter_by_deadline(self, queryset):

        deadline_param = self.request.query_params.get('deadline')


        if not deadline_param:
            return queryset
        now = timezone.now()
        today_start = timezone.make_aware(datetime.combine(now.date(), datetime.min.time()))
        deadline_map = {
            'today': today_start + timedelta(days=1),
            'tomorrow': today_start + timedelta(days=2),
            'week': today_start + timedelta(days=7),
            'month': today_start + timedelta(days=30),
        }
        target_end_time = deadline_map.get(deadline_param.lower())
        if target_end_time:
            return queryset.filter(
                (Q(status='INPROGRESS') & Q(deadline__lt=now)) |
                (Q(status='DONE') & Q(end_time__gt=F('deadline')))
            )
        return queryset


    def list(self, request, *args, **kwargs):
        return super().list(request, *args, **kwargs)

    def retrieve(self, request, *args, **kwargs):
        return super().retrieve(request, *args, **kwargs)


    def perform_create(self, serializer):
        assigned_to_user = serializer.validated_data.get('assigned_to')

        if assigned_to_user is not None:
            initial_status = 'TODO'
        else:
            initial_status = 'UNASSIGNED'

        serializer.save(
            supervisor=self.request.user,
            user=self.request.user,
            status=initial_status
        )



    def perform_update(self, serializer):
        status = self.request.data.get('status')
        instance = self.get_object()
        if status == 'INPROGRESS' and not instance.start_time:
            serializer.save(start_time=timezone.now())
        elif status == 'DONE':
            now = timezone.now()
            actual_dur = now - instance.start_time if instance.start_time else None
            serializer.save(end_time=now, actual_duration=actual_dur)
        else:
            serializer.save()



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
        if task.assigned_to is not None:
            return Response(
                {"error": f"This task is already assigned to {task.assigned_to.username}."},
                status=status.HTTP_400_BAD_REQUEST
            )

        task.assigned_to = request.user
        task.status = 'TODO'
        task.save()

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
        sent_fields = set(request.data.keys())
        task = self.get_object()
        if not sent_fields.issubset({'status'}):
            return Response(
                {"error": "You are not allowed to modify any field other than the task status."},
                status=status.HTTP_400_BAD_REQUEST
            )

        status_value = request.data.get('status')
        current_status = task.status
        allowed_choices = ['TODO', 'INPROGRESS', 'DONE']

        if status_value and status_value not in allowed_choices:
            return Response(
                {"error": f"The provided status is invalid. Allowed choices are: {allowed_choices}"},
                status=status.HTTP_400_BAD_REQUEST
            )


        if current_status == 'DONE' and status_value in ['INPROGRESS', 'TODO']:
            return Response(
                {"error": "You cannot make a task back, it is currently 'DONE'."},
                status=status.HTTP_400_BAD_REQUEST
            )

        is_project_admin = ProjectRole.objects.filter(project=task.project,user=request.user,role='ADMIN').exists()

        if request.user != task.assigned_to and request.user != task.supervisor and not is_project_admin:
            return Response(
                {"error": "You do not have permission to update the status of this task. Only the assigned employee or the project manager can change it."},
                status=status.HTTP_403_FORBIDDEN
            )


        if status_value == 'INPROGRESS' and not task.start_time:
            task.start_time = timezone.now()

        elif status_value == 'DONE':
            if not task.start_time:
                task.start_time = timezone.now()

            task.end_time = timezone.now()
            task.actual_duration = task.end_time - task.start_time

        task.status = status_value
        task.save()

        return Response(
            {"message": f"Task status updated successfully to {status_value}."},
            status=status.HTTP_200_OK
        )



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

        try:
            system_bot = User.objects.get(username='system_bot')
        except User.DoesNotExist:
            return Response([], status=status.HTTP_200_OK)

        orphaned_tasks = Task.objects.filter(project=project, supervisor=system_bot)

        serializer = TaskSerializer(orphaned_tasks, many=True)

        return Response(serializer.data, status=status.HTTP_200_OK)




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


        new_supervisor_id = request.data.get('new_supervisor_id')
        if not new_supervisor_id:
            return Response(
                {"error": "New supervisor ID is required."},
                status=status.HTTP_400_BAD_REQUEST
            )


        new_supervisor = get_object_or_404(User, id=new_supervisor_id)

        try:
            system_bot = User.objects.get(username='system_bot')
        except User.DoesNotExist:
            return Response(
                {"error": "System bot user has not been initialized yet. No tasks to transfer."},
                status=status.HTTP_404_NOT_FOUND
            )

        bot_tasks = Task.objects.filter(project=project, supervisor=system_bot)
        tasks_count = bot_tasks.count()
        if tasks_count == 0:
            return Response(
                {"message": "No orphaned tasks found under system_bot for this project."},
                status=status.HTTP_200_OK
            )

        bot_tasks.update(supervisor=new_supervisor)

        return Response(
            {
                "message": f"Successfully transferred {tasks_count} tasks to '{new_supervisor.username}'."
            },
            status=status.HTTP_200_OK
        )

