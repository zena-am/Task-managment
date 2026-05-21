from django.db.models import Q, Count
from django.utils import timezone
from datetime import datetime, timedelta
from users.errors.exceptions import InvalidPriorityError, InvalidStatusError
from users.models import Task


class TaskQueryService:

    @staticmethod
    def get_user_tasks(user, params):
        queryset = Task.objects.filter(assigned_to=user).distinct()

        queryset = TaskQueryService.filter_by_status(queryset, params.get("status"))
        queryset = TaskQueryService.filter_by_priority(queryset, params.get("priority"))
        queryset = TaskQueryService.filter_by_deadline(queryset, params.get("deadline"))

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
            (Q(status="INPROGRESS") & Q(deadline__lt=now)) |
            (Q(status="DONE") & Q(end_time__gt=F("deadline")))
        )




class TaskQueryService:

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