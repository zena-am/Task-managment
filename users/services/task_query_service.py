from datetime import datetime, timedelta

from django.db.models import F, Q, Count
from django.utils import timezone

from users.errors.exceptions import InvalidPriorityError, InvalidStatusError
from users.models import ProjectRole, Task, WorkSpaceMember


class TaskQueryService:
    @staticmethod
    def get_user_tasks(user, params):
        params = params or {}

        project_id = params.get("project_id")

        queryset = Task.objects.filter(assigned_to=user)

        if project_id:
            queryset = queryset.filter(project_id=project_id)

        queryset = TaskQueryService.filter_by_status(queryset, params.get("status"))
        queryset = TaskQueryService.filter_by_priority(queryset, params.get("priority"))
        queryset = TaskQueryService.filter_by_deadline(queryset, params.get("deadline"))

        return queryset.order_by("-id")

    @staticmethod
    def get_user_tasks_in_workspace(user, workspace_id, project_id, params=None):
        params = params or {}
        is_admin = WorkSpaceMember.objects.filter(
            workspace_id=workspace_id,
            user=user,
            role='ADMIN',
        ).exists()
        is_manager = ProjectRole.objects.filter(
            project_id=project_id,
            user=user,
            role__in=['ADMIN', 'MANAGER'],
        ).exists()

        if is_admin or is_manager:
            queryset = Task.objects.filter(project_id=project_id).distinct()
        else:
            queryset = Task.objects.filter(project_id=project_id, assigned_to=user).distinct()

        queryset = TaskQueryService.filter_by_status(queryset, params.get("status"))
        queryset = TaskQueryService.filter_by_priority(queryset, params.get("priority"))
        queryset = TaskQueryService.filter_by_deadline(queryset, params.get("deadline"))
        return queryset.order_by("-id")

    def get_tasks(user, params=None, workspace_id=None, project_id=None):
        params = params or {}

        is_manager = ProjectRole.objects.filter(
            user=user,
            role__in=['ADMIN', 'MANAGER'],
        ).exists()

        queryset = Task.objects.all()

        # 🔥 مهم جداً: الأساس دائماً
        if is_manager and project_id:
            queryset = queryset.filter(project_id=project_id)
        else:
            queryset = queryset.filter(assigned_to=user)

        # filters
        queryset = TaskQueryService.filter_by_status(queryset, params.get("status"))
        queryset = TaskQueryService.filter_by_priority(queryset, params.get("priority"))
        queryset = TaskQueryService.filter_by_deadline(queryset, params.get("deadline"))

        return queryset.order_by("-id")
    @staticmethod
    def get_tasks(user, params=None, workspace_id=None, project_id=None):
            params = params or {}

            queryset = Task.objects.all()

            is_admin_ws = False
            is_manager_project = False

            if workspace_id:
                is_admin_ws = WorkSpaceMember.objects.filter(
                    workspace_id=workspace_id,
                    user=user,
                    role='ADMIN',
                ).exists()

            if project_id:
                is_manager_project = ProjectRole.objects.filter(
                    project_id=project_id,
                    user=user,
                    role__in=['ADMIN', 'MANAGER'],
                ).exists()

            # 🎯 CORE RULE
            if is_admin_ws or is_manager_project:
                queryset = queryset.filter(
                    Q(project_id=project_id) if project_id else Q()
                )
            else:
                queryset = queryset.filter(assigned_to=user)

            # filters
            queryset = TaskQueryService.filter_by_status(queryset, params.get("status"))
            queryset = TaskQueryService.filter_by_priority(queryset, params.get("priority"))
            queryset = TaskQueryService.filter_by_deadline(queryset, params.get("deadline"))

            return queryset.order_by("-id")

    @staticmethod
    def filter_by_status(queryset, status_param):
        allowed = ["UNASSIGNED", "TODO", "INPROGRESS", "REVIEW", "DONE"]

        if not status_param:
            return queryset

        status_param = status_param.upper()
        if status_param not in allowed:
            raise InvalidStatusError()

        return queryset.filter(status=status_param)

    @staticmethod
    def filter_by_priority(queryset, priority_param):
        if not priority_param:
            return queryset

        priority_map = {
            "low": "L",
            "l": "L",
            "medium": "M",
            "m": "M",
            "high": "H",
            "h": "H",
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
        tomorrow_start = today_start + timedelta(days=1)
        after_tomorrow_start = today_start + timedelta(days=2)

        deadline_param = deadline_param.lower()

        if deadline_param == "late":
            return queryset.filter(due_date__lt=now).exclude(status="DONE")

        if deadline_param == "today":
            return queryset.filter(due_date__gte=today_start, due_date__lt=tomorrow_start)

        if deadline_param == "tomorrow":
            return queryset.filter(due_date__gte=tomorrow_start, due_date__lt=after_tomorrow_start)

        if deadline_param == "week":
            return queryset.filter(due_date__gte=now, due_date__lt=today_start + timedelta(days=7))

        if deadline_param == "month":
            return queryset.filter(due_date__gte=now, due_date__lt=today_start + timedelta(days=30))

        return queryset


class TaskCart:
    @staticmethod
    def get_user_card_stats(user):
        stats = Task.objects.filter(assigned_to=user).aggregate(
            todo_count=Count('id', filter=Q(status='TODO')),
            in_progress_count=Count('id', filter=Q(status='INPROGRESS')),
            review_count=Count('id', filter=Q(status='REVIEW')),
            completed_count=Count('id', filter=Q(status='DONE')),
        )

        return {
            "todo_tasks_count": stats['todo_count'] or 0,
            "in_progress_tasks_count": stats['in_progress_count'] or 0,
            "review_tasks_count": stats['review_count'] or 0,
            "completed_tasks_count": stats['completed_count'] or 0,
        }










class ProjectTaskCart:
    @staticmethod
    def get_project_card_stats(user, project):
        is_manager = ProjectRole.objects.filter(
            project=project,
            user=user,
            role__in=["MANAGER", "ADMIN"],
        ).exists()

        all_tasks_stats = Task.objects.filter(project=project).aggregate(
            todo_count=Count('id', filter=Q(status='TODO')),
            in_progress_count=Count('id', filter=Q(status='INPROGRESS')),
            review_count=Count('id', filter=Q(status='REVIEW')),
            completed_count=Count('id', filter=Q(status='DONE')),
        )

        user_tasks_stats = Task.objects.filter(project=project, assigned_to=user).aggregate(
            todo_count=Count('id', filter=Q(status='TODO')),
            in_progress_count=Count('id', filter=Q(status='INPROGRESS')),
            review_count=Count('id', filter=Q(status='REVIEW')),
            completed_count=Count('id', filter=Q(status='DONE')),
        )

        team_tasks_stats = None
        if is_manager:
            team_tasks_stats = Task.objects.filter(project=project).aggregate(
                todo_count=Count('id', filter=Q(status='TODO')),
                in_progress_count=Count('id', filter=Q(status='INPROGRESS')),
                review_count=Count('id', filter=Q(status='REVIEW')),
                completed_count=Count('id', filter=Q(status='DONE')),
            )

        return {
            "project_total_tasks": {
                "todo": all_tasks_stats['todo_count'] or 0,
                "in_progress": all_tasks_stats['in_progress_count'] or 0,
                "review": all_tasks_stats['review_count'] or 0,
                "completed": all_tasks_stats['completed_count'] or 0,
            },
            "my_tasks": {
                "todo": user_tasks_stats['todo_count'] or 0,
                "in_progress": user_tasks_stats['in_progress_count'] or 0,
                "review": user_tasks_stats['review_count'] or 0,
                "completed": user_tasks_stats['completed_count'] or 0,
            },
            "team_tasks": {
                "todo": team_tasks_stats['todo_count'] or 0,
                "in_progress": team_tasks_stats['in_progress_count'] or 0,
                "review": team_tasks_stats['review_count'] or 0,
                "completed": team_tasks_stats['completed_count'] or 0,
            } if team_tasks_stats else None,
        }
