from django.db.models import F, Q, Count
from django.utils import timezone
from datetime import datetime, timedelta
from users.errors.exceptions import InvalidPriorityError, InvalidStatusError
from users.models import ProjectRole, Task, WorkSpaceMember


class TaskQueryService:

    @staticmethod
    def get_user_tasks(user, params):
        params = params or {}
        queryset = Task.objects.filter(assigned_to=user).distinct()
        #querysetWithDone = Task.objects.filter(assigned_to=user).distinct()

        queryset = TaskQueryService.filter_by_status(queryset, params.get("status"))
        queryset = TaskQueryService.filter_by_priority(queryset, params.get("priority"))
        queryset = TaskQueryService.filter_by_LateDue_date(queryset, params.get("deadline"))
        return queryset.order_by("-id")


    @staticmethod
    def get_user_tasks_in_workspace(user, workspace_id,project_id, params=None):
        params = params or {}
        is_admin = WorkSpaceMember.objects.filter(workspace_id=workspace_id,user=user,role='ADMIN').select_related('workspace').exists()
        is_manager = ProjectRole.objects.filter(project_id=project_id,user=user,role='MANAGER').select_related('project').exists()

        if is_admin or is_manager:
            queryset = Task.objects.filter(project_id=project_id).distinct()
        else:
            queryset = Task.objects.filter(project_id=project_id,assigned_to=user).distinct()

        queryset = TaskQueryService.filter_by_status(queryset, params.get("status"))
        queryset = TaskQueryService.filter_by_priority(queryset, params.get("priority"))
        queryset = TaskQueryService.filter_by_LateDue_date(queryset, params.get("deadline"))
        return queryset.order_by("-id")


    @staticmethod
    def filter_by_status(queryset, status_param):
        allowed = ["TODO", "INPROGRESS", "DONE"]

        if not status_param:
            return queryset

        if status_param not in allowed:
            raise InvalidStatusError()

        return queryset.filter(status=status_param)

    @staticmethod
    def filter_by_priority(queryset, priority_param):

        if not priority_param:
            return queryset

        priority_map = {
            "low": "L",
            "medium": "M",
            "high": "H"
        }

        mapped = priority_map.get(priority_param.lower())

        if not mapped:
            raise InvalidPriorityError()

        return queryset.filter(priority=mapped)


    @staticmethod
    def filter_by_deadline(queryset, deadline_param):

        if not deadline_param:
            return queryset

        now = timezone.now()
        today_start = timezone.make_aware(datetime.combine(now.date(), datetime.min.time()))

        deadline_map = {
            "today": today_start + timedelta(days=1),
            "tomorrow": today_start + timedelta(days=2),
            "week": today_start + timedelta(days=7),
            "month": today_start + timedelta(days=30),
        }

        target = deadline_map.get(deadline_param.lower())


        if not target:
            return queryset

        return queryset.filter(
            due_date__gte=now,
            due_date__lt=target)


    @staticmethod
    def filter_by_LateDue_date(queryset, deadline_param):

        if deadline_param != "late":
            return queryset

        now = timezone.now()

        return queryset.filter(
        Q(status="INPROGRESS", due_date__lt=now) |
        Q(status="DONE", end_time__gt=F("due_date"))
    )




class TaskCart:

    @staticmethod
    def get_user_card_stats(user):
        stats = Task.objects.filter(assigned_to=user).aggregate(
            todo_count=Count('id', filter=Q(status='TODO')),
            in_progress_count=Count('id', filter=Q(status='INPROGRESS')),
            completed_count=Count('id', filter=Q(status='DONE'))
        )

        return {
            "todo_tasks_count": stats['todo_count'] or 0,
            "in_progress_tasks_count": stats['in_progress_count'] or 0,
            "completed_tasks_count": stats['completed_count'] or 0
        }

class ProjectTaskCart:

    @staticmethod
    def get_project_card_stats(user, project):
        is_manager = ProjectRole.objects.filter(
            project=project,
            user=user,
            role__in=["MANAGER", "ADMIN"]
        ).exists()

        all_tasks_stats = Task.objects.filter(project=project).aggregate(
            todo_count=Count('id', filter=Q(status='TODO')),
            in_progress_count=Count('id', filter=Q(status='INPROGRESS')),
            completed_count=Count('id', filter=Q(status='DONE'))
        )

        user_tasks_stats = Task.objects.filter(project=project, assigned_to=user).aggregate(
            todo_count=Count('id', filter=Q(status='TODO')),
            in_progress_count=Count('id', filter=Q(status='INPROGRESS')),
            completed_count=Count('id', filter=Q(status='DONE'))
        )

        if is_manager:
            team_tasks_stats = Task.objects.filter(project=project).aggregate(
                todo_count=Count('id', filter=Q(status='TODO')),
                in_progress_count=Count('id', filter=Q(status='INPROGRESS')),
                completed_count=Count('id', filter=Q(status='DONE'))
            )
        else:
            team_tasks_stats = None

        return {
            "project_total_tasks": {
                "todo": all_tasks_stats['todo_count'] or 0,
                "in_progress": all_tasks_stats['in_progress_count'] or 0,
                "completed": all_tasks_stats['completed_count'] or 0
            },
            "my_tasks": {
                "todo": user_tasks_stats['todo_count'] or 0,
                "in_progress": user_tasks_stats['in_progress_count'] or 0,
                "completed": user_tasks_stats['completed_count'] or 0
            },
            "team_tasks": {
                "todo": team_tasks_stats['todo_count'] or 0,
                "in_progress": team_tasks_stats['in_progress_count'] or 0,
                "completed": team_tasks_stats['completed_count'] or 0
            } if team_tasks_stats else None
        }