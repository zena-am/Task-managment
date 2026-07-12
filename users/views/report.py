from rest_framework import viewsets, permissions
from rest_framework.parsers import MultiPartParser, FormParser
from users.permissions import  RequestFormPermission, TechnicalReportPermission
from users.errors.messages.success import success_response
from users.serializers.report import ManagerRequestReviewSerializer
from users.services.bugService import BugReportService
from ..models import ProjectRole, TechnicalReportForm, RequestForm, BugReportForm, Invitation
from ..serializers import (TechnicalReportSerializer, RequestFormSerializer,BugReportSerializer, InvitationSerializer)
from ..services.report_service import FormService, ReportService
from rest_framework.decorators import action
from rest_framework.response import Response
from ..models import ProjectRole,Project, User
from rest_framework.views import APIView
from ..models import RequestForm
from ..serializers import  RequestFormSerializer
from rest_framework.permissions import IsAuthenticated
from django.shortcuts import get_object_or_404
from rest_framework import viewsets, permissions, status
from django.db.models import Q
from drf_spectacular.utils import (extend_schema,extend_schema_view,OpenApiExample,OpenApiResponse)
from drf_spectacular.types import OpenApiTypes


@extend_schema_view(

    list=extend_schema(
        tags=["التقارير التقنية"],
        summary="عرض التقارير التقنية",
        description=(
            "يعرض قائمة التقارير التقنية. "
            "إذا كان المستخدم مديرًا أو أدمن في مشاريع معينة، يتم عرض تقارير هذه المشاريع بالإضافة إلى تقاريره الشخصية. "
            "أما الموظف العادي فيرى تقاريره فقط."
        ),
        responses={200: TechnicalReportSerializer(many=True)},
    ),

    retrieve=extend_schema(
        tags=["التقارير التقنية"],
        summary="عرض تفاصيل تقرير تقني",
        description=(
            "يعرض تفاصيل تقرير تقني محدد، مثل المهمة المرتبطة، الوصف، الملفات، الصورة، الحالة، "
            "وتقييم المدير إن وجد."
        ),
        responses={200: TechnicalReportSerializer},
    ),

    create=extend_schema(
        tags=["التقارير التقنية"],
        summary="حفظ تقرير تقني كمسودة",
        description=(
            "ينشئ الموظف تقريرًا تقنيًا كمسودة DRAFT فقط. "
            "لا يتم إرسال التقرير للمدير في هذه المرحلة، ولا تتغير حالة المهمة. "
            "يجب أن تكون المهمة مسندة للموظف الحالي وحالتها INPROGRESS."
        ),
        request=TechnicalReportSerializer,
        responses={201: TechnicalReportSerializer},
        examples=[
            OpenApiExample(
                "مثال إنشاء مسودة تقرير",
                value={
                    "task": 5,
                    "description": "تم البدء بتنفيذ API تسجيل الدخول.",
                    "duration_time": "02:30:00",
                    "url": "https://github.com/example/pull/1",
                },
                request_only=True,
            )
        ],
    ),

    update=extend_schema(
        tags=["التقارير التقنية"],
        summary="تعديل تقرير تقني",
        description=(
            "يسمح للموظف بتعديل تقريره التقني فقط إذا كان التقرير ما زال في حالة DRAFT. "
            "لا يمكن تعديل التقرير بعد إرساله أو قبوله أو رفضه."
        ),
        request=TechnicalReportSerializer,
        responses={200: TechnicalReportSerializer},
    ),

    partial_update=extend_schema(
        tags=["التقارير التقنية"],
        summary="تعديل جزئي لتقرير تقني",
        description=(
            "يسمح بتعديل بعض حقول التقرير التقني فقط إذا كان التقرير في حالة DRAFT. "
            "يستخدم هذا الرابط لتحديث الوصف أو الرابط أو المرفقات قبل الإرسال."
        ),
        request=TechnicalReportSerializer,
        responses={200: TechnicalReportSerializer},
    ),

    destroy=extend_schema(
        tags=["التقارير التقنية"],
        summary="حذف تقرير تقني",
        description=(
            "يسمح للموظف بحذف تقريره التقني فقط إذا كان التقرير في حالة DRAFT. "
            "لا يمكن حذف تقرير SUBMITTED أو APPROVED أو REJECTED."
        ),
        responses={204: OpenApiResponse(description="تم حذف التقرير بنجاح.")},
    ),

)
class BaseSubmissionViewSet(viewsets.ModelViewSet):
    permission_classes = [permissions.IsAuthenticated]
    parser_classes = (MultiPartParser, FormParser)

    def _response_code_prefix(self):
        return self.__class__.__name__.replace('ViewSet', '').upper()

    def list(self, request, *args, **kwargs):
        queryset = self.filter_queryset(self.get_queryset())
        
        page = self.paginate_queryset(queryset)
        if page is not None:
            serializer = self.get_serializer(page, many=True)
            paginated = self.paginator.get_paginated_response(serializer.data)
            return Response(success_response(
                message="Items retrieved successfully",
                code="ITEMS_RETRIEVED",
                data=paginated.data,
            ), status=status.HTTP_200_OK)

        serializer = self.get_serializer(queryset, many=True)
        return Response(success_response(
            message="List retrieved successfully",
            code=f"{self._response_code_prefix()}_LIST_RETRIEVED",
            data=serializer.data,
        ), status=status.HTTP_200_OK)

    def retrieve(self, request, *args, **kwargs):
        instance = self.get_object()
        serializer = self.get_serializer(instance)
        return Response(success_response(
            message="Item retrieved successfully",
            code=f"{self._response_code_prefix()}_RETRIEVED",
            data=serializer.data,
        ), status=status.HTTP_200_OK)

    def create(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        self.perform_create(serializer)
        response_serializer = self.get_serializer(serializer.instance)
        return Response(success_response(
            message="Item created successfully",
            code=f"{self._response_code_prefix()}_CREATED",
            data=response_serializer.data,
        ), status=status.HTTP_201_CREATED)

    def update(self, request, *args, **kwargs):
        partial = kwargs.pop('partial', False)
        instance = self.get_object()
        serializer = self.get_serializer(instance, data=request.data, partial=partial)
        serializer.is_valid(raise_exception=True)
        self.perform_update(serializer)
        response_serializer = self.get_serializer(serializer.instance)
        return Response(success_response(
            message="Item updated successfully",
            code=f"{self._response_code_prefix()}_UPDATED",
            data=response_serializer.data,
        ), status=status.HTTP_200_OK)

    def partial_update(self, request, *args, **kwargs):
        kwargs['partial'] = True
        return self.update(request, *args, **kwargs)

    def destroy(self, request, *args, **kwargs):
        instance = self.get_object()
        object_id = instance.id
        self.perform_destroy(instance)
        return Response(success_response(
            message="Item deleted successfully",
            code=f"{self._response_code_prefix()}_DELETED",
            data={"id": object_id},
        ), status=status.HTTP_200_OK)




class TechnicalReportViewSet(BaseSubmissionViewSet):
    permission_classes = [
        IsAuthenticated,
        TechnicalReportPermission
    ]
    queryset = TechnicalReportForm.objects.all()
    serializer_class = TechnicalReportSerializer

    def get_queryset(self):
        user = self.request.user

        project_id = self.request.query_params.get("project")
        task_id = self.request.query_params.get("task")

        managed_projects = ProjectRole.objects.filter(
            user=user,
            role__in=["ADMIN", "MANAGER"]
        ).values_list("project_id", flat=True)

        if managed_projects.exists():
            queryset = self.queryset.filter(
                Q(task__project_id__in=managed_projects) | Q(user=user)
            )
        else:
            queryset = self.queryset.filter(user=user)

        if project_id:
            queryset = queryset.filter(task__project_id=project_id)

        if task_id:
            queryset = queryset.filter(task_id=task_id)

        return queryset.select_related(
            "task",
            "user",
            "task__project"
        ).order_by("-created_at")

    def perform_create(self, serializer):
        ReportService.save_technical_report_draft(
            serializer=serializer,
            user=self.request.user
        )

    def perform_update(self, serializer):
        ReportService.update_technical_report_draft(
            report=self.get_object(),
            serializer=serializer,
            user=self.request.user
        )

    def perform_destroy(self, instance):
        ReportService.delete_technical_report_draft(
            report=instance,
            user=self.request.user
        )
    @extend_schema(
        tags=["التقارير التقنية"],
        summary="إرسال التقرير التقني للمدير",
        description=(
            "يرسل الموظف التقرير التقني بعد حفظه كمسودة. "
            "عند الإرسال تتحول حالة التقرير إلى SUBMITTED، وتتحول حالة المهمة المرتبطة إلى REVIEW، "
            "ويتم إرسال إشعار لكل المدراء أو المشرفين المرتبطين بالمهمة."
        ),
        request=None,
        responses={200: TechnicalReportSerializer},
        examples=[
            OpenApiExample(
                "إرسال التقرير",
                value={
                    "id": 12,
                    "status": "SUBMITTED",
                    "task": 5,
                    "description": "تم تنفيذ API تسجيل الدخول."
                },
                response_only=True,
            )
        ],
    )
    @action(detail=True, methods=["patch"], url_path="submit")
    def submit(self, request, pk=None):
        report = self.get_object()

        report = ReportService.submit_technical_report(
            report=report,
            user=request.user
        )

        serializer = self.get_serializer(report)

        return Response(
    success_response(
        message="تم إرسال التقرير التقني بنجاح",
        code="TECHNICAL_REPORT_SUBMITTED_SUCCESS",
        data=serializer.data
    ),
    status=status.HTTP_200_OK
)




############################################################################################################
@extend_schema_view(
    list=extend_schema(
        tags=["طلبات الموظفين"],
        summary="عرض  طلبات الموظفين",
        description=(
            "يعرض طلبات المستخدم الحالي. "
            "إذا كان المستخدم مديرًا أو أدمن في مشاريع معينة، يتم عرض الطلبات المرتبطة بهذه المشاريع "
            "بالإضافة إلى طلباته الشخصية. أما الموظف العادي فيرى طلباته فقط."
        ),
        responses={200: RequestFormSerializer(many=True)},
    ),
    retrieve=extend_schema(
        tags=["طلبات الموظفين"],
        summary="عرض تفاصيل طلب",
        description=(
            "يعرض تفاصيل طلب محدد، مثل نوع الطلب، الأولوية، المشروع، السبب، الوقت، المرفقات، "
            "الحالة، وملاحظة المدير إن وجدت."
        ),
        responses={200: RequestFormSerializer},
    ),
    create=extend_schema(
        tags=["طلبات الموظفين"],
        summary="إنشاء طلب جديد",
        description=(
            "يسمح للموظف بإنشاء طلب جديد مثل طلب إجازة، مورد، صلاحية وصول، دعم فني، أو طلب آخر. "
            "يتم إنشاء الطلب بحالة  تلقائيًا.PENDING ثم يتم إرسال إشعار إلى مدراء المشرو"
        ),
        request=RequestFormSerializer,
        responses={201: RequestFormSerializer},
        examples=[
            OpenApiExample(
                "مثال إنشاء طلب إجازة",
                value={
                    "request_type": "LEAVE",
                    "priority": "NORMAL",
                    "project": 3,
                    "title": "طلب إجازة",
                    "reason": "أحتاج إجازة ليوم واحد.",
                    "time": "2026-06-10T09:00:00Z"
                },
                request_only=True,
            )
        ],
    ),
    update=extend_schema(
        tags=["طلبات الموظفين"],
        summary="تعديل طلب",
        description=(
            "يسمح بتعديل الطلب فقط PENDING إذا كان الطلب في حال"
            "لا يمكن تعديل الطلب بعد قبوله أو رفضه من المدير"
        ),
        request=RequestFormSerializer,
        responses={200: RequestFormSerializer},
    ),
    partial_update=extend_schema(
        tags=["طلبات الموظفين"],
        summary="تعديل جزئي لطلب",
        description=(
            "يسمح بتعديل بعض حقول الطلب فقط   مثل السبب أو الوقت أو المرفقات. PENDINGإذا كانت حالته"
        ),
        request=RequestFormSerializer,
        responses={200: RequestFormSerializer},
    ),
    destroy=extend_schema(
        tags=["طلبات الموظفين"],
        summary="حذف طلب",
        description=(
            "يسمح بحذف الطلب فقط إذا كان في حالة PENDING. "
            "لا يمكن حذف الطلب بعد قبوله أو رفضه."
        ),
        responses={204: OpenApiResponse(description="تم حذف الطلب بنجاح.")},
    ),
)

class RequestFormViewSet(BaseSubmissionViewSet):
        permission_classes = [
        IsAuthenticated,
        RequestFormPermission
        ]

        queryset = RequestForm.objects.all()
        serializer_class = RequestFormSerializer

        def get_queryset(self):
            user = self.request.user

            managed_projects = ProjectRole.objects.filter(
                user=user,
                role__in=["ADMIN", "MANAGER"]
            ).values_list("project_id", flat=True)

            if managed_projects.exists():
                return self.queryset.filter(
                    Q(project_id__in=managed_projects) | Q(user=user)
                ).select_related(
                    "project",
                    "user"
                ).order_by("-created_at")

            return self.queryset.filter(
                user=user
            ).select_related(
                "project"
            ).order_by("-created_at")

        def perform_create(self, serializer):
            FormService.create_request_form(
                serializer=serializer,
                user=self.request.user
            )

        def perform_update(self, serializer):
            FormService.update_request_form(
                request_form=self.get_object(),
                serializer=serializer,
                user=self.request.user
            )

        def perform_destroy(self, instance):
            FormService.delete_request_form(
                request_form=instance,
                user=self.request.user
            )
        @extend_schema(
            tags=["طلبات الموظفين"],
            summary="قبول أو رفض طلب موظف",
            description=(
                "يسمح للمدير أو الأدمن بمراجعة طلب موظف داخل مشروع يديره. "
                "يمكنه تغيير حالة الطلب إلى APPROVED أو REJECTED، مع إضافة ملاحظة في manager_feedback."
            ),
            request=ManagerRequestReviewSerializer,
            responses={200: RequestFormSerializer},
            examples=[
        OpenApiExample(
            "قبول الطلب",
            value={
                "status": "APPROVED",
                "manager_feedback": "تمت الموافقة على الطلب."
            },
            request_only=True,
        ),
        OpenApiExample(
            "رفض الطلب",
            value={
                "status": "REJECTED",
                "manager_feedback": "تم رفض الطلب بسبب ضغط العمل في هذا التاريخ."
            },
            request_only=True,
        ),
    ],
        )
        @action(detail=True, methods=["patch"], url_path="review")
        def review(self, request, pk=None):
            request_form = self.get_object()

            serializer = ManagerRequestReviewSerializer(
                instance=request_form,
                data=request.data,
                partial=True
            )

            serializer.is_valid(raise_exception=True)

            request_form = FormService.review_request_form(
                request_form=request_form,
                manager_user=request.user,
                status_value=serializer.validated_data.get("status"),
                manager_feedback=serializer.validated_data.get("manager_feedback")
            )

            response_serializer = self.get_serializer(request_form)

            return Response(
    success_response(
        message=" REQUEST_REVIEWED_SUCCESS ",
        code="REQUEST_REVIEWED_SUCCESS",
        data=response_serializer.data
    ),
    status=status.HTTP_200_OK
)


######################################################################################################

class BugReportViewSet(BaseSubmissionViewSet):
    permission_classes = [IsAuthenticated]
    parser_classes = [MultiPartParser, FormParser]

    queryset = BugReportForm.objects.all()
    serializer_class = BugReportSerializer

    def get_queryset(self):
        user = self.request.user

        managed_project_ids = ProjectRole.objects.filter(
            user=user,
            role__in=["ADMIN", "MANAGER"],
        ).values_list(
            "project_id",
            flat=True,
        )

        return self.queryset.filter(
            Q(user=user)
            | Q(project_id__in=managed_project_ids)
            | Q(task__assigned_to=user)
        ).select_related(
            "project",
            "user",
            "task",
            "task__assigned_to",
        ).distinct().order_by("-created_at")

    def perform_create(self, serializer):
        BugReportService.create_bug(
            serializer=serializer,
            user=self.request.user,
        )

    def perform_update(self, serializer):
        BugReportService.update_bug(
            bug=self.get_object(),
            serializer=serializer,
            user=self.request.user,
        )

    def perform_destroy(self, instance):
        BugReportService.delete_bug(
            bug=instance,
            user=self.request.user,
        )

    @action(
        detail=True,
        methods=["post"],
        url_path="convert-to-task",
    )
    def convert_to_task(self, request, pk=None):
        bug = self.get_object()

        serializer = BugToTaskSerializer(
            data=request.data,
            context={
                "request": request,
                "bug": bug,
            },
        )
        serializer.is_valid(raise_exception=True)

        task = BugReportService.convert_to_task(
            bug=bug,
            manager=request.user,
            assigned_to=serializer.validated_data.get(
                "assigned_to"
            ),
            expected_duration=serializer.validated_data[
                "expected_duration"
            ],
            due_date=serializer.validated_data["due_date"],
            priority=serializer.validated_data.get("priority"),
        )

        return Response(
            success_response(
                message="Bug report converted to task successfully.",
                code="BUG_CONVERTED_TO_TASK",
                data={
                    "bug_id": bug.id,
                    "task_id": task.id,
                    "assigned_to": task.assigned_to_id,
                },
            ),
            status=status.HTTP_201_CREATED,
        )

    @action(
        detail=True,
        methods=["patch"],
        url_path="verify",
    )
    def verify(self, request, pk=None):
        bug = BugReportService.verify_fix(
            bug=self.get_object(),
            user=request.user,
        )

        return Response(
            success_response(
                message="Bug fix verified successfully.",
                code="BUG_VERIFIED",
                data=self.get_serializer(bug).data,
            ),
            status=status.HTTP_200_OK,
        )

    @action(
        detail=True,
        methods=["patch"],
        url_path="close",
    )
    def close(self, request, pk=None):
        bug = BugReportService.close_bug(
            bug=self.get_object(),
            manager=request.user,
            result=request.data.get("result"),
        )

        return Response(
            success_response(
                message="Bug report closed successfully.",
                code="BUG_CLOSED",
                data=self.get_serializer(bug).data,
            ),
            status=status.HTTP_200_OK,
        )