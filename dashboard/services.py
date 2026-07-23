from django.db import transaction
from django.utils import timezone
from rest_framework.exceptions import PermissionDenied, ValidationError

from users.models import ActivityLog, ProjectRole, Task, User
from .selectors import get_managed_projects, get_managed_workspaces


def _log(user, action, action_id, changes):
    ActivityLog.objects.create(user=user, action=action, action_id=action_id, changes=changes)


def managed_tasks_queryset(user):
    project_ids = get_managed_projects(user).values_list("id", flat=True)
    return Task.objects.filter(project_id__in=project_ids)


@transaction.atomic
def bulk_update_tasks(user, validated_data):
    ids = validated_data["task_ids"]
    tasks = list(managed_tasks_queryset(user).select_related("project").filter(id__in=ids))
    found_ids = {task.id for task in tasks}
    missing = sorted(set(ids) - found_ids)
    if missing:
        raise PermissionDenied("Some tasks were not found or are outside your management scope: %s" % missing)

    action = validated_data["action"]
    employee = None
    if action in ("assign", "reassign"):
        employee = User.objects.filter(pk=validated_data["employee_id"]).first()
        if employee is None:
            raise ValidationError({"employee_id": "User not found."})
        invalid_projects = [
            task.project_id for task in tasks
            if not ProjectRole.objects.filter(project_id=task.project_id, user=employee).exists()
        ]
        if invalid_projects:
            raise ValidationError({"employee_id": "The employee is not a member of every selected task project."})

    now = timezone.now()
    changed = []
    for task in tasks:
        before = {
            "assigned_to_id": task.assigned_to_id,
            "status": task.status,
            "priority": task.priority,
            "is_archived": task.is_archived,
            "is_deleted": task.is_deleted,
        }
        if action in ("assign", "reassign"):
            task.assigned_to = employee
            task.assignment_state = "ASSIGNED"
        elif action == "change_status":
            task.status = validated_data["status"]
            if task.status == "DONE" and task.end_time is None:
                task.end_time = now
        elif action == "change_priority":
            task.priority = validated_data["priority"]
        elif action == "archive":
            task.is_archived = True
            task.archived_at = now
            task.archived_by = user
        elif action == "restore":
            task.is_archived = False
            task.archived_at = None
            task.archived_by = None
        elif action == "delete":
            task.is_deleted = True
            task.deleted_at = now
            task.deleted_by = user
        task.save()
        after = {
            "assigned_to_id": task.assigned_to_id,
            "status": task.status,
            "priority": task.priority,
            "is_archived": task.is_archived,
            "is_deleted": task.is_deleted,
        }
        changed.append({"id": task.id, "before": before, "after": after})

    _log(user, "BULK_TASK_UPDATED", tasks[0].id, {"action": action, "tasks": changed})
    return {"action": action, "updated_count": len(tasks), "task_ids": sorted(found_ids)}


@transaction.atomic
def set_archive_state(user, resource, object_id, archive):
    now = timezone.now()
    if resource == "workspace":
        obj = get_managed_workspaces(user).filter(pk=object_id).first()
    elif resource == "project":
        obj = get_managed_projects(user).filter(pk=object_id).first()
    elif resource == "task":
        obj = managed_tasks_queryset(user).filter(pk=object_id).first()
    else:
        raise ValidationError({"resource": "Unsupported resource."})
    if obj is None:
        raise PermissionDenied("Object was not found or is outside your management scope.")

    obj.is_archived = archive
    obj.archived_at = now if archive else None
    obj.archived_by = user if archive else None
    obj.save(update_fields=["is_archived", "archived_at", "archived_by", "updated_at"])
    action = "%s_%s" % (resource.upper(), "ARCHIVED" if archive else "RESTORED")
    _log(user, action, obj.id, {"resource": resource, "is_archived": archive})
    return {"resource": resource, "id": obj.id, "is_archived": obj.is_archived, "archived_at": obj.archived_at}
