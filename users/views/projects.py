from django.db import transaction
from drf_spectacular.utils import extend_schema, extend_schema_view
from rest_framework import permissions, status, viewsets
from rest_framework.decorators import action
from rest_framework.response import Response

from users.errors.exceptions import BaseAppException
from users.errors.messages.success import success_response
from users.models import Project, ProjectRole, Task
from users.services.project_logic import ProjectServiceLogic as ProjectService
from ..permissions import IsProjectManagerOrReadOnly
from ..serializers import ProjectSerializer, ProjectCreateSerializer


@extend_schema_view(
    list=extend_schema(tags=['المشاريع'], summary="جلب قائمة المشاريع"),
    retrieve=extend_schema(tags=['المشاريع'], summary="جلب تفاصيل مشروع"),
    create=extend_schema(tags=['المشاريع'], summary="إنشاء مشروع جديد"),
    partial_update=extend_schema(tags=['المشاريع'], summary="تعديل جزئي لمشروع"),
    destroy=extend_schema(tags=['المشاريع'], summary="حذف مشروع"),
)
class ProjectViewSet(viewsets.ModelViewSet):
    permission_classes = [permissions.IsAuthenticated, IsProjectManagerOrReadOnly]
    serializer_class = ProjectSerializer

    def get_serializer_class(self):
        if self.action in ['create', 'update', 'partial_update']:
            return ProjectCreateSerializer
        return ProjectSerializer

    def get_queryset(self):
        queryset = Project.objects.filter(
            workspace__members=self.request.user,
        ).select_related('workspace').distinct()

        workspace_id = self.request.query_params.get('workspace')
        if workspace_id:
            queryset = queryset.filter(workspace_id=workspace_id)

        return queryset

    def list(self, request, *args, **kwargs):
        queryset = self.filter_queryset(self.get_queryset())
        page = self.paginate_queryset(queryset)
        if page is not None:
            serializer = ProjectSerializer(page, many=True, context=self.get_serializer_context())
            paginated = self.paginator.get_paginated_response(serializer.data)
            return Response(success_response(
                message="Projects retrieved successfully",
                code="PROJECTS_RETRIEVED",
                data=paginated.data,
            ), status=status.HTTP_200_OK)

        serializer = ProjectSerializer(queryset, many=True, context=self.get_serializer_context())
        return Response(success_response(
            message="Projects retrieved successfully",
            code="PROJECTS_RETRIEVED",
            data=serializer.data,
        ), status=status.HTTP_200_OK)

    def retrieve(self, request, *args, **kwargs):
        project = self.get_object()
        serializer = ProjectSerializer(project, context=self.get_serializer_context())
        return Response(success_response(
            message="Project retrieved successfully",
            code="PROJECT_RETRIEVED",
            data=serializer.data,
        ), status=status.HTTP_200_OK)

    def create(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        result = ProjectService.create(serializer, request)
        project_serializer = ProjectSerializer(result['project'], context=self.get_serializer_context())

        return Response(success_response(
            message="Project created successfully",
            code="PROJECT_CREATED",
            data={
                "project": project_serializer.data,
                "invitation_results": result.get("invitation_results"),
            },
        ), status=status.HTTP_201_CREATED)

    def update(self, request, *args, **kwargs):
        partial = kwargs.pop('partial', False)
        instance = self.get_object()
        serializer = self.get_serializer(instance, data=request.data, partial=partial)
        serializer.is_valid(raise_exception=True)
        project = serializer.save()
        response_serializer = ProjectSerializer(project, context=self.get_serializer_context())
        return Response(success_response(
            message="Project updated successfully",
            code="PROJECT_UPDATED",
            data=response_serializer.data,
        ), status=status.HTTP_200_OK)

    def partial_update(self, request, *args, **kwargs):
        kwargs['partial'] = True
        return self.update(request, *args, **kwargs)

    def destroy(self, request, *args, **kwargs):
        instance = self.get_object()
        project_id = instance.id
        self.perform_destroy(instance)
        return Response(success_response(
            message="Project deleted successfully",
            code="PROJECT_DELETED",
            data={"project_id": project_id},
        ), status=status.HTTP_200_OK)

    @extend_schema(
        tags=['المشاريع'],
        summary="مغادرة المشروع",
        description="يسمح للمستخدم الحالي بمغادرة المشروع فقط دون مغادرة مساحة العمل",
    )
    @action(detail=True, methods=['delete'], url_path='leave')
    def leave_project(self, request, pk=None):
        project = self.get_object()
        user = request.user

        member_role = ProjectRole.objects.filter(project=project, user=user).first()
        if not member_role:
            raise BaseAppException(
                detail="أنت لست عضواً في هذا المشروع.",
                code="PROJECT_NOT_MEMBER",
                status_code=400,
            )

        if member_role.role in ['ADMIN', 'MANAGER']:
            has_other_manager = ProjectRole.objects.filter(
                project=project,
                role__in=['ADMIN', 'MANAGER'],
            ).exclude(user=user).exists()

            if not has_other_manager:
                raise BaseAppException(
                    detail="لا يمكنك مغادرة المشروع لأنك آخر مدير/أدمن. يجب تعيين مدير آخر أولاً.",
                    code="LAST_PROJECT_MANAGER_CANNOT_LEAVE",
                    status_code=400,
                )

        with transaction.atomic():
            Task.objects.filter(project=project, assigned_to=user).update(
                assigned_to=None,
                status="UNASSIGNED",
            )
            member_role.delete()

        return Response(success_response(
            message="Left project successfully",
            code="PROJECT_LEFT",
            data={"project_id": project.id},
        ), status=status.HTTP_200_OK)
