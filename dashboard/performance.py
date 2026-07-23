from collections import defaultdict
from datetime import timedelta

from django.db.models import Q
from django.utils import timezone

from users.models import ProjectRole, Task, TechnicalReportForm, User, WorkSpaceMember

from .selectors import get_managed_projects, get_managed_workspaces


def validate_project_access(user, project_id):
    return get_managed_projects(user).filter(pk=project_id).select_related("workspace").first()


def get_scope_projects(user, workspace=None, project=None):
    queryset = get_managed_projects(user)
    if workspace is not None:
        queryset = queryset.filter(workspace=workspace)
    if project is not None:
        queryset = queryset.filter(pk=project.pk)
    return queryset.select_related("workspace")


def get_scope_employee_ids(projects, workspace=None):
    ids = set(ProjectRole.objects.filter(project__in=projects).values_list("user_id", flat=True))
    if workspace is not None:
        ids.update(WorkSpaceMember.objects.filter(workspace=workspace).values_list("user_id", flat=True))
    return ids


def _seconds(value):
    return value.total_seconds() if value is not None else None


def _average(values):
    values = [value for value in values if value is not None]
    if not values:
        return None
    return round(sum(values) / len(values), 2)


def _completion_rate(completed, total):
    return round((completed / total) * 100, 2) if total else 0.0


def _task_queryset(projects, date_from=None, date_to=None):
    queryset = Task.objects.filter(project__in=projects, is_deleted=False)
    if date_from:
        queryset = queryset.filter(created_at__date__gte=date_from)
    if date_to:
        queryset = queryset.filter(created_at__date__lte=date_to)
    return queryset


def _report_queryset(projects, date_from=None, date_to=None):
    queryset = TechnicalReportForm.objects.filter(task__project__in=projects)
    if date_from:
        queryset = queryset.filter(created_at__date__gte=date_from)
    if date_to:
        queryset = queryset.filter(created_at__date__lte=date_to)
    return queryset


def employee_metrics(employee, projects, date_from=None, date_to=None):
    tasks = _task_queryset(projects, date_from, date_to).filter(assigned_to=employee)
    reports = _report_queryset(projects, date_from, date_to).filter(user=employee)
    now = timezone.now()

    total = tasks.count()
    completed = tasks.filter(status="DONE").count()
    overdue = tasks.filter(due_date__lt=now).exclude(status="DONE").count()
    in_progress = tasks.filter(status="INPROGRESS").count()
    review = tasks.filter(status="REVIEW").count()
    todo = tasks.filter(status="TODO").count()

    durations = []
    for task in tasks.filter(status="DONE").only(
        "actual_duration", "start_time", "end_time", "created_at"
    ):
        if task.actual_duration is not None:
            durations.append(_seconds(task.actual_duration))
        elif task.end_time is not None:
            start = task.start_time or task.created_at
            if start and task.end_time >= start:
                durations.append((task.end_time - start).total_seconds())

    expected = [_seconds(value) for value in tasks.values_list("expected_duration", flat=True)]
    actual = [_seconds(value) for value in tasks.values_list("actual_duration", flat=True)]

    project_rows = []
    roles = {
        row.project_id: row.role
        for row in ProjectRole.objects.filter(user=employee, project__in=projects)
    }
    for project in projects:
        project_tasks = tasks.filter(project=project)
        project_total = project_tasks.count()
        project_completed = project_tasks.filter(status="DONE").count()
        if project_total or project.id in roles:
            project_rows.append(
                {
                    "id": project.id,
                    "name": project.name,
                    "workspace": {
                        "id": project.workspace_id,
                        "name": project.workspace.name if project.workspace else None,
                    },
                    "role": roles.get(project.id),
                    "assigned_tasks": project_total,
                    "completed_tasks": project_completed,
                    "overdue_tasks": project_tasks.filter(due_date__lt=now)
                    .exclude(status="DONE")
                    .count(),
                    "completion_rate": _completion_rate(project_completed, project_total),
                }
            )

    workspace_map = defaultdict(lambda: {"projects": 0, "assigned_tasks": 0, "completed_tasks": 0})
    for row in project_rows:
        workspace = row["workspace"]
        if not workspace["id"]:
            continue
        item = workspace_map[(workspace["id"], workspace["name"])]
        item["projects"] += 1
        item["assigned_tasks"] += row["assigned_tasks"]
        item["completed_tasks"] += row["completed_tasks"]

    workspaces = []
    for (workspace_id, workspace_name), values in workspace_map.items():
        workspaces.append(
            {
                "id": workspace_id,
                "name": workspace_name,
                "projects": values["projects"],
                "assigned_tasks": values["assigned_tasks"],
                "completed_tasks": values["completed_tasks"],
                "completion_rate": _completion_rate(
                    values["completed_tasks"], values["assigned_tasks"]
                ),
            }
        )

    return {
        "employee": {
            "id": employee.id,
            "username": employee.username,
            "full_name": f"{employee.first_name} {employee.last_name}".strip()
            or employee.username,
            "email": employee.email,
            "avatar": employee.avatar.url if employee.avatar else None,
        },
        "workspaces": sorted(workspaces, key=lambda item: item["name"] or ""),
        "projects": sorted(project_rows, key=lambda item: item["name"]),
        "tasks": {
            "assigned": total,
            "todo": todo,
            "in_progress": in_progress,
            "review": review,
            "completed": completed,
            "overdue": overdue,
            "completion_rate": _completion_rate(completed, total),
        },
        "reports": {
            "total": reports.count(),
            "draft": reports.filter(status="DRAFT").count(),
            "submitted": reports.filter(status="SUBMITTED").count(),
            "approved": reports.filter(status="APPROVED").count(),
            "rejected": reports.filter(status="REJECTED").count(),
            "approval_rate": _completion_rate(
                reports.filter(status="APPROVED").count(),
                reports.filter(status__in=["APPROVED", "REJECTED"]).count(),
            ),
        },
        "time": {
            "average_completion_seconds": _average(durations),
            "average_expected_seconds": _average(expected),
            "average_actual_seconds": _average(actual),
        },
    }


def get_performance(user, workspace=None, project=None, employee_id=None, date_from=None, date_to=None):
    projects = list(get_scope_projects(user, workspace, project))
    employee_ids = get_scope_employee_ids(projects, workspace)
    if employee_id is not None:
        employee_ids.intersection_update({employee_id})

    employees = User.objects.filter(id__in=employee_ids).order_by("first_name", "last_name", "username")
    rows = [employee_metrics(employee, projects, date_from, date_to) for employee in employees]
    rows.sort(
        key=lambda row: (
            -row["tasks"]["completion_rate"],
            -row["tasks"]["completed"],
            row["employee"]["full_name"].lower(),
        )
    )
    return {
        "scope": {
            "workspace": (
                {"id": workspace.id, "name": workspace.name} if workspace else None
            ),
            "project": (
                {
                    "id": project.id,
                    "name": project.name,
                    "workspace_id": project.workspace_id,
                }
                if project
                else None
            ),
            "date_from": date_from,
            "date_to": date_to,
        },
        "employees_count": len(rows),
        "results": rows,
    }


def get_employee_performance(user, employee_id, workspace=None, project=None, date_from=None, date_to=None):
    projects = list(get_scope_projects(user, workspace, project))
    allowed_ids = get_scope_employee_ids(projects, workspace)
    if employee_id not in allowed_ids:
        return None
    employee = User.objects.filter(pk=employee_id).first()
    if employee is None:
        return None
    return employee_metrics(employee, projects, date_from, date_to)


def get_charts(user, workspace=None, project=None, employee_id=None, date_from=None, date_to=None):
    projects = get_scope_projects(user, workspace, project)
    tasks = _task_queryset(projects, date_from, date_to)
    reports = _report_queryset(projects, date_from, date_to)
    if employee_id is not None:
        tasks = tasks.filter(assigned_to_id=employee_id)
        reports = reports.filter(user_id=employee_id)

    status_labels = ["TODO", "INPROGRESS", "REVIEW", "DONE"]
    priority_labels = ["L", "M", "H"]
    report_labels = ["DRAFT", "SUBMITTED", "APPROVED", "REJECTED"]

    today = timezone.localdate()
    timeline = []
    for offset in range(29, -1, -1):
        day = today - timedelta(days=offset)
        timeline.append(
            {
                "date": day,
                "created": tasks.filter(created_at__date=day).count(),
                "completed": tasks.filter(status="DONE", end_time__date=day).count(),
            }
        )

    return {
        "scope": {
            "workspace_id": workspace.id if workspace else None,
            "project_id": project.id if project else None,
            "employee_id": employee_id,
            "date_from": date_from,
            "date_to": date_to,
        },
        "tasks_by_status": [
            {"key": key, "label": dict(Task.STATUS_CHOICES)[key], "value": tasks.filter(status=key).count()}
            for key in status_labels
        ],
        "tasks_by_priority": [
            {"key": key, "label": dict(Task.PRIORITY_CHOICES)[key], "value": tasks.filter(priority=key).count()}
            for key in priority_labels
        ],
        "reports_by_status": [
            {"key": key, "label": dict(TechnicalReportForm.REPORT_STATUS)[key], "value": reports.filter(status=key).count()}
            for key in report_labels
        ],
        "tasks_timeline_30_days": timeline,
    }
