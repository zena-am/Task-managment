from datetime import timedelta

from django.db.models import Q
from django.utils import timezone

from users.models import (
    ActivityLog,
    BugReportForm,
    Project,
    ProjectRole,
    RequestForm,
    Task,
    TechnicalReportForm,
    User,
    WorkSpace,
    WorkSpaceMember,
)


def get_managed_workspaces(user):
    if user.is_superuser:
        return WorkSpace.objects.all()

    return WorkSpace.objects.filter(
        Q(workspacemember__user=user, workspacemember__role="ADMIN")
        | Q(
            projects__projectrole__user=user,
            projects__projectrole__role__in=["ADMIN", "MANAGER"],
        )
    ).distinct()


def get_managed_projects(user, workspace_id=None):
    if user.is_superuser:
        queryset = Project.objects.all()
    else:
        admin_workspace_ids = WorkSpaceMember.objects.filter(
            user=user,
            role="ADMIN",
        ).values_list("workspace_id", flat=True)

        queryset = Project.objects.filter(
            Q(workspace_id__in=admin_workspace_ids)
            | Q(projectrole__user=user, projectrole__role__in=["ADMIN", "MANAGER"])
        ).distinct()

    if workspace_id is not None:
        queryset = queryset.filter(workspace_id=workspace_id)
    return queryset


def validate_workspace_access(user, workspace_id):
    if workspace_id is None:
        return None
    return get_managed_workspaces(user).filter(pk=workspace_id).first()


def get_overview(user, workspace=None):
    projects = get_managed_projects(user, workspace.id if workspace else None)
    project_ids = projects.values_list("id", flat=True)
    tasks = Task.objects.filter(project_id__in=project_ids, is_deleted=False)
    reports = TechnicalReportForm.objects.filter(task__project_id__in=project_ids)
    requests = RequestForm.objects.filter(project_id__in=project_ids)
    bugs = BugReportForm.objects.filter(project_id__in=project_ids)

    if workspace:
        workspaces = WorkSpace.objects.filter(pk=workspace.pk)
    else:
        workspaces = get_managed_workspaces(user)

    now = timezone.now()
    upcoming = now + timedelta(days=7)
    member_ids = set(
        WorkSpaceMember.objects.filter(workspace__in=workspaces).values_list(
            "user_id", flat=True
        )
    )
    member_ids.update(
        ProjectRole.objects.filter(project_id__in=project_ids).values_list(
            "user_id", flat=True
        )
    )

    return {
        "scope": {
            "workspace_id": workspace.id if workspace else None,
            "workspace_name": workspace.name if workspace else None,
        },
        "workspaces_count": workspaces.count(),
        "projects_count": projects.count(),
        "members_count": User.objects.filter(id__in=member_ids).count(),
        "tasks": {
            "total": tasks.count(),
            "todo": tasks.filter(status="TODO").count(),
            "in_progress": tasks.filter(status="INPROGRESS").count(),
            "review": tasks.filter(status="REVIEW").count(),
            "completed": tasks.filter(status="DONE").count(),
            "overdue": tasks.filter(due_date__lt=now).exclude(status="DONE").count(),
            "due_soon": tasks.filter(
                due_date__gte=now,
                due_date__lte=upcoming,
            ).exclude(status="DONE").count(),
            "unassigned": tasks.filter(assigned_to__isnull=True).count(),
        },
        "reports": {
            "total": reports.count(),
            "draft": reports.filter(status="DRAFT").count(),
            "submitted": reports.filter(status="SUBMITTED").count(),
            "approved": reports.filter(status="APPROVED").count(),
            "rejected": reports.filter(status="REJECTED").count(),
        },
        "requests": {
            "total": requests.count(),
            "pending": requests.filter(status="PENDING").count(),
            "approved": requests.filter(status="APPROVED").count(),
            "rejected": requests.filter(status="REJECTED").count(),
        },
        "bugs": {
            "total": bugs.count(),
            "open": bugs.filter(status="OPEN").count(),
            "fixed": bugs.filter(status="FIXED").count(),
            "verified": bugs.filter(status="VERIFIED").count(),
            "closed": bugs.filter(status="CLOSED").count(),
        },
    }


def get_activity_queryset(user, workspace=None, employee_id=None, action=None, date_from=None, date_to=None):
    projects = get_managed_projects(user, workspace.id if workspace else None)
    managed_user_ids = set(
        ProjectRole.objects.filter(project__in=projects).values_list("user_id", flat=True)
    )
    managed_user_ids.update(
        WorkSpaceMember.objects.filter(
            workspace__in=(WorkSpace.objects.filter(pk=workspace.pk) if workspace else get_managed_workspaces(user))
        ).values_list("user_id", flat=True)
    )
    managed_user_ids.add(user.id)

    queryset = ActivityLog.objects.select_related("user").filter(user_id__in=managed_user_ids)
    if employee_id is not None:
        queryset = queryset.filter(user_id=employee_id)
    if action:
        queryset = queryset.filter(action=action)
    if date_from:
        queryset = queryset.filter(created_at__date__gte=date_from)
    if date_to:
        queryset = queryset.filter(created_at__date__lte=date_to)
    return queryset.order_by("-created_at")
