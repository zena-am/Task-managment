from datetime import datetime, timedelta

from django.db.models import F, Q, Count
from django.utils import timezone
from rest_framework.exceptions import ValidationError
from users.errors.exceptions import InvalidPriorityError, InvalidStatusError, PermissionDeniedError
from users.models import Project, ProjectRole, Task, WorkSpace, WorkSpaceMember


class TaskQueryService:
    @staticmethod
    def get_user_tasks(user, params):
        params = params or {}
        params.get("archived"),
        project_id = params.get("project_id")

        queryset = Task.objects.filter(assigned_to=user)

        if project_id:
            queryset = queryset.filter(project_id=project_id)

        queryset = TaskQueryService.filter_by_status(queryset, params.get("status"))
        queryset = TaskQueryService.filter_by_priority(queryset, params.get("priority"))
        queryset = TaskQueryService.filter_by_deadline(queryset, params.get("deadline"))
        queryset = TaskQueryService.filter_by_archived(
            queryset,
            params.get("archived"),
        )
        return queryset.order_by("-id")

    @staticmethod
    def get_user_workspace_tasks_grouped(
        *,
        user,
        workspace_id,
        params=None,
    ):
        params = params or {}

        is_workspace_member = WorkSpaceMember.objects.filter(
            workspace_id=workspace_id,
            user=user,
        ).exists()

        if not is_workspace_member:
            raise PermissionDeniedError()

        projects = Project.objects.filter(
            workspace_id=workspace_id,
            projectrole__user=user,
        ).distinct().order_by("-id")

        result = []
        total_tasks = 0

        for project in projects:
            tasks = Task.objects.filter(
                project=project,
                assigned_to=user,
                is_deleted=False,
            ).select_related(
                "project",
                "assigned_to",
            )

            tasks = TaskQueryService.filter_by_status(
                tasks,
                params.get("status"),
            )

            tasks = TaskQueryService.filter_by_priority(
                tasks,
                params.get("priority"),
            )

            tasks = TaskQueryService.filter_by_deadline(
                tasks,
                params.get("deadline"),
            )

            tasks = TaskQueryService.filter_by_archived(
                tasks,
                params.get("archived"),
            )

            tasks = tasks.order_by("-id")
            tasks_count = tasks.count()
            total_tasks += tasks_count

            result.append({
                "project": project,
                "tasks": tasks,
                "tasks_count": tasks_count,
            })

        return {
            "workspace_id": int(workspace_id),
            "projects": result,
            "total_tasks": total_tasks,
        }
    @staticmethod
    def get_tasks(
        user,
        params=None,
        workspace_id=None,
        project_id=None,
    ):
        params = params or {}

        project_id = (
            project_id
            or params.get("project")
            or params.get("project_id")
        )

        workspace_id = (
            workspace_id
            or params.get("workspace")
            or params.get("workspace_id")
        )

        queryset = Task.objects.filter(
            is_deleted=False,
        )

        if project_id:
            project_role = ProjectRole.objects.filter(
                project_id=project_id,
                user=user,
            ).first()

            is_workspace_admin = WorkSpaceMember.objects.filter(
                workspace_id=workspace_id,
                user=user,
                role="ADMIN",
            ).exists() if workspace_id else False

            if (
                is_workspace_admin
                or (
                    project_role
                    and project_role.role in ["ADMIN", "MANAGER"]
                )
            ):
                queryset = queryset.filter(
                    project_id=project_id,
                )

            else:
                queryset = queryset.filter(
                    project_id=project_id,
                    assigned_to=user,
                )

        elif workspace_id:
            is_workspace_admin = WorkSpaceMember.objects.filter(
                workspace_id=workspace_id,
                user=user,
                role="ADMIN",
            ).exists()

            if is_workspace_admin:
                queryset = queryset.filter(
                    project__workspace_id=workspace_id,
                )
            else:
                allowed_project_ids = ProjectRole.objects.filter(
                    user=user,
                    project__workspace_id=workspace_id,
                ).values_list(
                    "project_id",
                    flat=True,
                )

                queryset = queryset.filter(
                    Q(
                        project_id__in=allowed_project_ids,
                        assigned_to=user,
                    )
                    | Q(
                        project_id__in=ProjectRole.objects.filter(
                            user=user,
                            role__in=["ADMIN", "MANAGER"],
                            project__workspace_id=workspace_id,
                        ).values_list(
                            "project_id",
                            flat=True,
                        )
                    )
                )

        else:
            managed_project_ids = ProjectRole.objects.filter(
                user=user,
                role__in=["ADMIN", "MANAGER"],
            ).values_list(
                "project_id",
                flat=True,
            )

            queryset = queryset.filter(
                Q(assigned_to=user)
                | Q(project_id__in=managed_project_ids)
            )

        queryset = TaskQueryService.filter_by_status(
            queryset,
            params.get("status"),
        )

        queryset = TaskQueryService.filter_by_priority(
            queryset,
            params.get("priority"),
        )

        queryset = TaskQueryService.filter_by_deadline(
            queryset,
            params.get("deadline"),
        )
        queryset = TaskQueryService.filter_by_archived(
        queryset,
        params.get("archived"),
    )

        return queryset.distinct().order_by("-id")

    @staticmethod
    def get_project_tasks(
        *,
        user,
        project_id,
        params=None,
    ):
        params = params or {}

        project_role = ProjectRole.objects.filter(
            project_id=project_id,
            user=user,
        ).values_list(
            "role",
            flat=True,
        ).first()

        is_workspace_owner = WorkSpaceMember.objects.filter(
            workspace__projects__id=project_id,
            workspace__creator=user,
        ).exists()

        if not project_role and not is_workspace_owner:
            raise PermissionDeniedError()

        queryset = Task.objects.filter(
            project_id=project_id,
            is_deleted=False,
        )

        can_view_all_tasks = (
            is_workspace_owner
            or project_role in [
                "ADMIN",
                "MANAGER",
            ]
        )

        if not can_view_all_tasks:
            queryset = queryset.filter(
                assigned_to=user,
            )

        queryset = TaskQueryService.filter_by_status(
            queryset,
            params.get("status"),
        )

        queryset = TaskQueryService.filter_by_priority(
            queryset,
            params.get("priority"),
        )

        queryset = TaskQueryService.filter_by_deadline(
            queryset,
            params.get("deadline"),
        )

        queryset = TaskQueryService.filter_by_archived(
            queryset,
            params.get("archived"),
        )

        return queryset.distinct().order_by("-id")

    @staticmethod
    def filter_by_status(queryset, status_param):
        if not status_param:
            return queryset

        status_param = status_param.upper()

        if status_param == "UNASSIGNED":
            return queryset.filter(
                assigned_to__isnull=True,
            )

        allowed = [
            "TODO",
            "INPROGRESS",
            "REVIEW",
            "DONE",
            "PAUSED",
        ]

        if status_param not in allowed:
            raise InvalidStatusError()

        return queryset.filter(
            status=status_param,
        )

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




    @staticmethod
    def filter_by_archived(
        queryset,
        archived_param,
    ):
        if archived_param is None:
            return queryset.filter(
                is_archived=False,
            )

        archived_value = str(
            archived_param
        ).strip().lower()

        if archived_value in [
            "true",
            "1",
            "yes",
        ]:
            return queryset.filter(
                is_archived=True,
            )

        if archived_value in [
            "false",
            "0",
            "no",
        ]:
            return queryset.filter(
                is_archived=False,
            )

        if archived_value == "all":
            return queryset

        raise ValidationError({
            "archived": (
                "Archived must be true, false, or all."
            )
        })
    @staticmethod
    def filter_by_priority(
        queryset,
        priority_param,
    ):
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

        priority = priority_map.get(
            str(priority_param).lower()
        )

        if not priority:
            raise InvalidPriorityError()

        return queryset.filter(
            priority=priority,
        )


















    @staticmethod
    def get_workspace_team_tasks_grouped(
        *,
        user,
        workspace_id,
        params=None,
    ):
        params = params or {}

        membership = WorkSpaceMember.objects.filter(
            workspace_id=workspace_id,
            user=user,
        ).first()

        is_workspace_owner = WorkSpace.objects.filter(
            id=workspace_id,
            creator=user,
        ).exists()

        is_workspace_admin = bool(
            membership
            and membership.role == "ADMIN"
        )

        if not (
            is_workspace_owner
            or is_workspace_admin
        ):
            raise PermissionDeniedError()

        members = (
            WorkSpaceMember.objects
            .filter(
                workspace_id=workspace_id,
                user__is_deleted=False,
            )
            .select_related("user")
            .order_by("user__username")
        )

        result_members = []
        total_tasks = 0

        for membership_item in members:
            member = membership_item.user

            projects = (
                Project.objects
                .filter(
                    workspace_id=workspace_id,
                    projectrole__user=member,
                )
                .distinct()
                .order_by("name")
            )

            project_results = []
            member_tasks_count = 0

            for project in projects:
                tasks = (
                    Task.objects
                    .filter(
                        project=project,
                        assigned_to=member,
                        is_deleted=False,
                    )
                    .select_related(
                        "project",
                        "assigned_to",
                    )
                )

                tasks = TaskQueryService.filter_by_status(
                    tasks,
                    params.get("status"),
                )

                tasks = TaskQueryService.filter_by_priority(
                    tasks,
                    params.get("priority"),
                )

                tasks = TaskQueryService.filter_by_deadline(
                    tasks,
                    params.get("deadline"),
                )

                tasks = TaskQueryService.filter_by_archived(
                    tasks,
                    params.get("archived"),
                )

                tasks = tasks.order_by("-id")
                tasks_count = tasks.count()

                if tasks_count == 0:
                    continue

                member_tasks_count += tasks_count

                project_results.append({
                    "project": project,
                    "tasks": tasks,
                    "tasks_count": tasks_count,
                })

            total_tasks += member_tasks_count

            result_members.append({
                "member": member,
                "workspace_role": membership_item.role,
                "tasks_count": member_tasks_count,
                "projects": project_results,
            })

        return {
            "workspace_id": int(workspace_id),
            "total_members": len(result_members),
            "total_tasks": total_tasks,
            "members": result_members,
        }












class TaskCart:

    @staticmethod
    def get_user_card_stats2(user):
            stats = Task.objects.filter(
                assigned_to=user,
                is_deleted=False,
                is_archived=False,
            ).aggregate(
                todo_count=Count(
                    "id",
                    filter=Q(status="TODO"),
                ),
                in_progress_count=Count(
                    "id",
                    filter=Q(
                        status="INPROGRESS"
                    ),
                ),
                review_count=Count(
                    "id",
                    filter=Q(status="REVIEW"),
                ),
                paused_count=Count(
                    "id",
                    filter=Q(status="PAUSED"),
                ),
                completed_count=Count(
                    "id",
                    filter=Q(status="DONE"),
                ),
            )

            return {
                "todo_tasks_count": (
                    stats["todo_count"] or 0
                ),
                "in_progress_tasks_count": (
                    stats["in_progress_count"] or 0
                ),
                "review_tasks_count": (
                    stats["review_count"] or 0
                ),
                "paused_tasks_count": (
                    stats["paused_count"] or 0
                ),
                "completed_tasks_count": (
                    stats["completed_count"] or 0
                ),
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
                is_deleted=False,
                is_archived=False,
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





