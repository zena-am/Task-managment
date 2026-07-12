from django.db.models import Q
from drf_spectacular.utils import extend_schema
from rest_framework import permissions, status, viewsets
from rest_framework.decorators import action
from rest_framework.response import Response

from users.errors.messages.success import success_response
from users.models import (
    Project,
    ProjectRole,
    WorkSpace,
    WorkSpaceMember,
)
from users.serializers import ProjectSerializer, WorkSpaceSerializer


@extend_schema(tags=["البحث في مساحات العمل"])
class WorkspaceSearchViewSet(viewsets.ReadOnlyModelViewSet):
    serializer_class = WorkSpaceSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        user = self.request.user

        managed_workspace_ids = ProjectRole.objects.filter(
            user=user,
            role__in=["ADMIN", "MANAGER"],
        ).values_list(
            "project__workspace_id",
            flat=True,
        )

        return WorkSpace.objects.filter(
            Q(creator=user)
            | Q(members=user)
            | Q(id__in=managed_workspace_ids),
        ).select_related(
            "creator",
        ).distinct().order_by(
            "-created_at",
        )

    @extend_schema(
        summary="البحث في مساحات العمل",
        description=(
            "يبحث ضمن مساحات العمل التي يستطيع المستخدم الوصول إليها فقط، "
            "ويشمل البحث اسم المساحة ووصفها واسم منشئها."
        ),
        responses={200: WorkSpaceSerializer(many=True)},
    )
    @action(
        detail=False,
        methods=["get"],
        url_path="search",
    )
    def search(self, request):
        query = request.query_params.get("q", "").strip()

        if len(query) < 2:
            return Response(
                success_response(
                    message="Search query must be at least 2 characters.",
                    code="SEARCH_QUERY_TOO_SHORT",
                    data=[],
                ),
                status=status.HTTP_200_OK,
            )

        workspaces = self.get_queryset().filter(
            Q(name__icontains=query)
            | Q(description__icontains=query)
            | Q(creator__username__icontains=query)
            | Q(creator__email__icontains=query)
        )[:20]

        serializer = self.get_serializer(
            workspaces,
            many=True,
            context={
                "request": request,
            },
        )

        return Response(
            success_response(
                message="Workspaces retrieved successfully.",
                code="WORKSPACE_SEARCH_RESULTS",
                data=serializer.data,
            ),
            status=status.HTTP_200_OK,
        )

    @extend_schema(
        summary="عرض مساحة عمل محددة",
        responses={200: WorkSpaceSerializer},
    )
    def retrieve(self, request, *args, **kwargs):
        workspace = self.get_object()

        serializer = self.get_serializer(
            workspace,
            context={
                "request": request,
            },
        )

        return Response(
            success_response(
                message="Workspace retrieved successfully.",
                code="WORKSPACE_RETRIEVED",
                data=serializer.data,
            ),
            status=status.HTTP_200_OK,
        )

    @extend_schema(
        summary="عرض مساحات العمل المتاحة للمستخدم",
        responses={200: WorkSpaceSerializer(many=True)},
    )
    def list(self, request, *args, **kwargs):
        queryset = self.filter_queryset(
            self.get_queryset(),
        )

        page = self.paginate_queryset(queryset)

        if page is not None:
            serializer = self.get_serializer(
                page,
                many=True,
                context={
                    "request": request,
                },
            )

            paginated_response = self.get_paginated_response(
                serializer.data,
            )

            return Response(
                success_response(
                    message="Workspaces retrieved successfully.",
                    code="WORKSPACES_RETRIEVED",
                    data=paginated_response.data,
                ),
                status=status.HTTP_200_OK,
            )

        serializer = self.get_serializer(
            queryset,
            many=True,
            context={
                "request": request,
            },
        )

        return Response(
            success_response(
                message="Workspaces retrieved successfully.",
                code="WORKSPACES_RETRIEVED",
                data=serializer.data,
            ),
            status=status.HTTP_200_OK,
        )


@extend_schema(tags=["البحث في المشاريع"])
class ProjectSearchViewSet(viewsets.ReadOnlyModelViewSet):
    serializer_class = ProjectSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        user = self.request.user

        workspace_ids = WorkSpaceMember.objects.filter(
            user=user,
        ).values_list(
            "workspace_id",
            flat=True,
        )

        return Project.objects.filter(
            Q(projectrole__user=user)
            | Q(workspace__creator=user)
            | Q(workspace_id__in=workspace_ids),
        ).select_related(
            "workspace",
            "workspace__creator",
        ).distinct().order_by(
            "-created_at",
        )

    @extend_schema(
        summary="البحث في المشاريع",
        description=(
            "يبحث ضمن المشاريع التي يستطيع المستخدم الوصول إليها فقط. "
            "يشمل البحث اسم المشروع ووصفه واسم مساحة العمل."
        ),
        responses={200: ProjectSerializer(many=True)},
    )
    @action(
        detail=False,
        methods=["get"],
        url_path="search",
    )
    def search(self, request):
        query = request.query_params.get("q", "").strip()
        workspace_id = request.query_params.get("workspace")

        if len(query) < 2:
            return Response(
                success_response(
                    message="Search query must be at least 2 characters.",
                    code="SEARCH_QUERY_TOO_SHORT",
                    data=[],
                ),
                status=status.HTTP_200_OK,
            )

        projects = self.get_queryset().filter(
            Q(name__icontains=query)
            | Q(description__icontains=query)
            | Q(workspace__name__icontains=query)
        )

        if workspace_id:
            try:
                workspace_id = int(workspace_id)
            except (TypeError, ValueError):
                return Response(
                    success_response(
                        message="Workspace id must be a valid integer.",
                        code="INVALID_WORKSPACE_ID",
                        data=[],
                    ),
                    status=status.HTTP_400_BAD_REQUEST,
                )

            projects = projects.filter(
                workspace_id=workspace_id,
            )

        projects = projects[:20]

        serializer = self.get_serializer(
            projects,
            many=True,
            context={
                "request": request,
            },
        )

        return Response(
            success_response(
                message="Projects retrieved successfully.",
                code="PROJECT_SEARCH_RESULTS",
                data=serializer.data,
            ),
            status=status.HTTP_200_OK,
        )

    @extend_schema(
        summary="عرض مشروع محدد",
        responses={200: ProjectSerializer},
    )
    def retrieve(self, request, *args, **kwargs):
        project = self.get_object()

        serializer = self.get_serializer(
            project,
            context={
                "request": request,
            },
        )

        return Response(
            success_response(
                message="Project retrieved successfully.",
                code="PROJECT_RETRIEVED",
                data=serializer.data,
            ),
            status=status.HTTP_200_OK,
        )

    @extend_schema(
        summary="عرض المشاريع المتاحة للمستخدم",
        responses={200: ProjectSerializer(many=True)},
    )
    def list(self, request, *args, **kwargs):
        queryset = self.filter_queryset(
            self.get_queryset(),
        )

        page = self.paginate_queryset(queryset)

        if page is not None:
            serializer = self.get_serializer(
                page,
                many=True,
                context={
                    "request": request,
                },
            )

            paginated_response = self.get_paginated_response(
                serializer.data,
            )

            return Response(
                success_response(
                    message="Projects retrieved successfully.",
                    code="PROJECTS_RETRIEVED",
                    data=paginated_response.data,
                ),
                status=status.HTTP_200_OK,
            )

        serializer = self.get_serializer(
            queryset,
            many=True,
            context={
                "request": request,
            },
        )

        return Response(
            success_response(
                message="Projects retrieved successfully.",
                code="PROJECTS_RETRIEVED",
                data=serializer.data,
            ),
            status=status.HTTP_200_OK,
        )