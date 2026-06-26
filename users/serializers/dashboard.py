from rest_framework import serializers
from django.utils import timezone
from datetime import timedelta
from django.db.models import Q, Count
from ..models import ProjectRole, Task, WorkSpace, ActivityLog
from django.utils.timesince import timesince
from users.models import User


class TopbarListSerializer(serializers.ModelSerializer):
        unread_notifications_count = serializers.SerializerMethodField()

        class Meta:
            model = User
            fields = ['id', 'username', 'avatar', 'unread_notifications_count']

        def get_unread_notifications_count(self, obj):
                return obj.notifications.filter(is_read=False).count()

class DashboardSerializer(serializers.Serializer):
    stats = serializers.SerializerMethodField()
    topbar = serializers.SerializerMethodField()
    action_label = serializers.SerializerMethodField()
    spaces = serializers.SerializerMethodField()
    #workspace = serializers.SerializerMethodField()
    urgent_alerts = serializers.SerializerMethodField()
    recent_activities = serializers.SerializerMethodField()



    def _get_accessible_workspaces(self, user, selected_workspace=None):
        admin_workspace_ids = ProjectRole.objects.filter(
            user=user,
            role='ADMIN'
        ).values_list('project__workspace_id', flat=True)

        workspaces = WorkSpace.objects.filter(
            Q(members=user) |
            Q(id__in=admin_workspace_ids)
        ).distinct()

        if selected_workspace is not None:
            workspaces = workspaces.filter(id=selected_workspace.id)

        return workspaces

    def get_topbar(self, obj):

        user = obj['user']
        return TopbarListSerializer(user, context=self.context).data

    def get_action_label(self, obj):
            user = obj['user']
            workspace = obj.get('workspace')
            now = timezone.now()

            admin_projects = ProjectRole.objects.filter(
                user=user,
                role='ADMIN'
            )

            if workspace is not None:
                admin_projects = admin_projects.filter(project__workspace=workspace)

            admin_project_ids = admin_projects.values_list('project_id', flat=True)

            is_manager = admin_projects.exists()

            team_overdue = Task.objects.filter(
                project_id__in=admin_project_ids,
                due_date__lt=now
            ).exclude(status='DONE').count() if is_manager else 0

            my_tasks = Task.objects.filter(assigned_to=user)

            if workspace is not None:
                my_tasks = my_tasks.filter(project__workspace=workspace)

            my_overdue = my_tasks.filter(
                due_date__lt=now
            ).exclude(status='DONE').count()

            if my_overdue > 0 and team_overdue > 0:
                return f"Critical status! You have {my_overdue} overdue personal tasks, and {team_overdue} delayed tasks in your team!"

            if my_overdue > 0:
                return f"Alert: You have {my_overdue} overdue personal tasks that need urgent action!"

            if team_overdue > 0:
                return f"Manager Alert: There are {team_overdue} overdue tasks in your team requiring immediate follow-up."

            pending_tasks = my_tasks.filter(status='TODO').count()

            if pending_tasks > 0:
                return f"You have {pending_tasks} pending tasks waiting to be started."

            if is_manager:
                return "All your projects and team members are running strictly on schedule!"

            return "Everything is running smoothly today!"
##################################################################
    def get_spaces(self, obj):
        user = obj['user']
        workspace = obj.get('workspace')
        now = timezone.now()

        workspaces = self._get_accessible_workspaces(user, workspace)

        problematic_spaces = []
        upcoming_deadline_threshold = now + timedelta(days=1)

        for w in workspaces:
            overdue_tasks_count = Task.objects.filter(
                project__workspace=w,
                due_date__lt=now
            ).exclude(status='DONE').count()

            if overdue_tasks_count > 0:
                problematic_spaces.append({
                    "id": w.id,
                    "name": w.name,
                    "overdue_count": overdue_tasks_count,
                    "status_color": "ALERT"
                })
                continue

            near_deadline_count = Task.objects.filter(
                project__workspace=w,
                due_date__gte=now,
                due_date__lte=upcoming_deadline_threshold
            ).exclude(status='DONE').count()

            if near_deadline_count > 0:
                problematic_spaces.append({
                    "id": w.id,
                    "name": w.name,
                    "overdue_count": 0,
                    "near_deadline_count": near_deadline_count,
                    "status_color": "WARNING"
                })
                continue

            active_tasks_count = Task.objects.filter(
                project__workspace=w
            ).exclude(status='DONE').count()

            if active_tasks_count > 0:
                problematic_spaces.append({
                    "id": w.id,
                    "name": w.name,
                    "overdue_count": 0,
                    "near_deadline_count": 0,
                    "active_tasks_count": active_tasks_count,
                    "status_color": "STABLE"
                })
                continue

            problematic_spaces.append({
                "id": w.id,
                "name": w.name,
                "overdue_count": 0,
                "near_deadline_count": 0,
                "active_tasks_count": 0,
                "status_color": "COMFORT"
            })

        return problematic_spaces

    def get_stats(self, obj):
        user = obj['user']
        workspace = obj.get('workspace')
        now = timezone.now()
        upcoming_threshold = now + timedelta(days=1)

        workspaces = self._get_accessible_workspaces(user, workspace)

        tasks = Task.objects.filter(
            project__workspace__in=workspaces
        )

        active_tasks_count = tasks.exclude(status='DONE').count()

        my_tasks_count = tasks.filter(
            assigned_to=user
        ).exclude(status='DONE').count()

        overdue_tasks_count = tasks.filter(
            due_date__lt=now
        ).exclude(status='DONE').count()

        near_deadline_tasks_count = tasks.filter(
            due_date__gte=now,
            due_date__lte=upcoming_threshold
        ).exclude(status='DONE').count()

        projects_count = workspaces.aggregate(
            count=Count('projects', distinct=True)
        )['count'] or 0

        return {
            "workspaces_count": workspaces.count(),
            "projects_count": projects_count,
            "active_tasks_count": active_tasks_count,
            "my_tasks_count": my_tasks_count,
            "overdue_tasks_count": overdue_tasks_count,
            "near_deadline_tasks_count": near_deadline_tasks_count,
        }

    ###################################################################

    def get_urgent_alerts(self, obj):
            user = obj['user']
            workspace = obj.get('workspace')
            now = timezone.now()
            upcoming_threshold = now + timedelta(days=1)

            alerts = []

            workspaces_queryset = self._get_accessible_workspaces(
                user,
                workspace
            ).annotate(
                project_overdue_count=Count(
                    'projects__tasks',
                    filter=Q(projects__tasks__priority='H') &
                        Q(projects__tasks__due_date__lt=now) &
                        ~Q(projects__tasks__status='DONE'),
                    distinct=True
                ),
                project_near_deadline_count_db=Count(
                    'projects__tasks',
                    filter=Q(projects__tasks__due_date__gte=now) &
                        Q(projects__tasks__due_date__lt=upcoming_threshold) &
                        ~Q(projects__tasks__status='DONE'),
                    distinct=True
                ),
                active_count_db=Count(
                    'projects__tasks',
                    filter=~Q(projects__tasks__status='DONE'),
                    distinct=True
                )
            )

            for w in workspaces_queryset:
                is_manager = ProjectRole.objects.filter(
                    user=user,
                    role='ADMIN',
                    project__workspace=w
                ).exists()

                if w.project_overdue_count > 0:
                    if is_manager:
                        alerts.append({
                            "space_id": w.id,
                            "type": "TEAM_DELAY",
                            "title": f"Delay in {w.name}",
                            "description": f"The workspace '{w.name}' has {w.project_overdue_count} overdue critical team tasks.",
                            "status_color": "ALERT"
                        })
                    else:
                        alerts.append({
                            "space_id": w.id,
                            "type": "PERSONAL_DEADLINE",
                            "title": f"Delay in {w.name}",
                            "description": f"The workspace '{w.name}' has {w.project_overdue_count} overdue tasks you need to check.",
                            "status_color": "ALERT"
                        })
                    continue

                if w.project_near_deadline_count_db > 0:
                    if is_manager:
                        alerts.append({
                            "space_id": w.id,
                            "type": "TEAM_DEADLINE",
                            "title": "Approaching Deadline",
                            "description": f"There are {w.project_near_deadline_count_db} upcoming tasks due soon in the workspace '{w.name}'.",
                            "status_color": "WARNING"
                        })
                    else:
                        alerts.append({
                            "space_id": w.id,
                            "type": "PERSONAL_DEADLINE",
                            "title": "Approaching Deadline",
                            "description": f"You have {w.project_near_deadline_count_db} tasks in workspace '{w.name}' that are approaching their deadline soon!",
                            "status_color": "WARNING"
                        })
                    continue

                if w.active_count_db > 0:
                    if is_manager:
                        alerts.append({
                            "space_id": w.id,
                            "type": "TEAM_STABLE",
                            "title": "Workspace Stable",
                            "description": f"The team has {w.active_count_db} active tasks in progress within '{w.name}'. Everything looks good!",
                            "status_color": "STABLE"
                        })
                    else:
                        alerts.append({
                            "space_id": w.id,
                            "type": "PERSONAL_PROGRESS",
                            "title": "Tasks In Progress",
                            "description": f"You have {w.active_count_db} active tasks currently in progress within '{w.name}'. Keep it up!",
                            "status_color": "STABLE"
                        })
                    continue

            if not alerts:
                alerts.append({
                    "space_id": None,
                    "type": "INFO",
                    "title": "No Alerts",
                    "description": "Your projects are perfectly stable, and there are no current issues.",
                    "status_color": "COMFORT"
                })

            return alerts


    def get_recent_activities(self, obj):
        user = obj['user']

        logs = ActivityLog.objects.filter(user=user).order_by('-id')[:5]
        return ActivityLogSerializer(logs, many=True, context=self.context).data





class ActivityLogSerializer(serializers.ModelSerializer):
    action_text = serializers.SerializerMethodField()
    time_ago = serializers.SerializerMethodField()

    class Meta:
        model = ActivityLog
        fields = ['id', 'action', 'action_id', 'action_text', 'time_ago']
    def get_action_text(self, obj):
        changes = obj.changes or {}

        subject = changes.get('subject_name', 'Someone')
        target = changes.get('target_title', 'System')
        reason = changes.get('reason', '')

        if obj.action == 'ACCOUNT_CREATED':
            return f"New account initialized for user '{subject}'."

        elif obj.action == 'TASK_ASSIGNED':
            return f"Task '{target}' successfully assigned to {subject}."

        elif obj.action == 'TASK_UNASSIGNED':
            return reason if reason else f"User {subject} was unassigned from task '{target}'."

        elif obj.action in ['MEMBER_REMOVED', 'MEMBER_LEFT']:
            return reason if reason else f"Member {subject} left workspace '{target}'."

        elif obj.action == 'ACCOUNT_PURGED':
            return f"Account of user '{subject}' was permanently deleted, impacting '{target}'."

        elif obj.action == 'GENERAL_UPDATE':
            return reason if reason else f"General update on '{target}'."


    def get_time_ago(self, obj):
                try:
                    now = timezone.now()
                    duration = timesince(obj.created_at, now)
                    main_part = duration.split(',')[0].strip()
                    return f"{main_part} ago"
                except Exception:
                    return "Just now"


