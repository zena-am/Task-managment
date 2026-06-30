from django.utils import timezone
from rest_framework.exceptions import ValidationError

from users.constants import create_activity_log, create_notification
from users.errors.exceptions import (
    InvalidStatusError,
    PermissionDeniedError,
    TaskAlreadyAssigned,
    TechnicalReportMissingError,
)
from users.models import ActivityLog, Notification, ProjectRole, Task, TechnicalReportForm, User
from users.services.invitationsService import InvitationService

TASK_TRANSITIONS = {
        "TODO": ["INPROGRESS"],
        "INPROGRESS": ["REVIEW", "TODO"],
        "REVIEW": ["DONE"],
        "DONE": []
}
def can_change_status(user, task):
        is_assignee = task.assigned_to_id == user.id

        is_manager = ProjectRole.objects.filter(
            project=task.project,
            user=user,
            role__in=["ADMIN", "MANAGER"],
        ).exists()

        return is_assignee or is_manager
def validate_review_transition(task):
        report = TechnicalReportForm.objects.filter(
            task=task,
            user=task.assigned_to,
            status="SUBMITTED",
        ).order_by("-created_at").first()

        if not report:
            raise TechnicalReportMissingError()

        return report
def handle_side_effects(task, user, new_status):
        if new_status == "INPROGRESS" and not task.start_time:
            task.start_time = timezone.now()

        if new_status == "DONE":
            task.end_time = timezone.now()
            if task.start_time:
                task.actual_duration = task.end_time - task.start_time
class TaskService:
    @staticmethod
    def claim_task(task, user):
        if task.assigned_to is not None:
            raise TaskAlreadyAssigned()

        is_project_member = ProjectRole.objects.filter(project=task.project, user=user).exists()
        if not is_project_member:
            raise PermissionDeniedError()

        task.assigned_to = user
        task.status = "TODO"
        task.save(update_fields=["assigned_to", "status", "updated_at"])

        managers = User.objects.filter(
            projectrole__project=task.project,
            projectrole__role__in=['ADMIN', 'MANAGER'],
        ).exclude(id=user.id).distinct()

        for manager in managers:
            create_notification(
                recipient=manager,
                notification_type="SYSTEM_ALERT",
                title="تم استلام مهمة",
                message=f"قام الموظف {user.username} باستلام المهمة: {task.title}",
                navigation_target=f"/tasks/{task.id}",
            )

        create_activity_log(
            user=user,
            action="GENERAL_UPDATE",
            action_id=task.id,
            subject_name=user.username,
            target_title=task.title,
            reason="Task claimed by employee",
            is_by_admin=False,
        )

        return task



    @staticmethod
    def create_task(user, serializer):
        assigned_user = serializer.validated_data.get('assigned_to')
        project = serializer.validated_data.get('project')
        initial_status = 'TODO' if assigned_user is not None else 'UNASSIGNED'
        task = serializer.save(creator=user, status=initial_status)

        if assigned_user:
            is_project_member = ProjectRole.objects.filter(project=project, user=assigned_user).exists()
            if not is_project_member:
                InvitationService.send_project_invitation(
                    sender=user,
                    data={
                        "project_id": task.project.id,
                        "receiver_emails": [assigned_user.email],
                        "role": "EMPLOYEE",
                    },
                )

            create_notification(
                recipient=assigned_user,
                notification_type="TASK_ASSIGNED",
                title="مهمة جديدة",
                message=f"قام {user.username} بإسناد مهمة جديدة لك: {task.title}",
                navigation_target=f"/tasks/{task.id}",
            )

        create_activity_log(
            user=user,
            action="GENERAL_UPDATE",
            action_id=task.id,
            subject_name=user.username,
            target_title=task.title,
            reason="Task created",
            is_by_admin=True,
        )

        return task

    """
    @staticmethod
    def update_status(task, user, status_value):

        allowed = TASK_TRANSITIONS.get(task.status, [])
        if status_value not in allowed:
            raise InvalidStatusError()

        if not can_change_status(user, task):
            raise PermissionDeniedError()

        if status_value == "REVIEW":
            validate_review_transition(task)

            managers = User.objects.filter(
                projectrole__project=task.project,
                projectrole__role__in=["ADMIN", "MANAGER"],
            ).distinct()

            for manager in managers:
                create_notification(
                    recipient=manager,
                    notification_type="REPORT_SUBMITTED",
                    title="New Technical Report Submitted",
                    message=f"Employee {user.username} submitted report for '{task.title}'",
                    navigation_target=f"/task_details/{task.id}",
                )

        handle_side_effects(task, user, status_value)

        task.status = status_value
        task.save(
            update_fields=[
                "status",
                "start_time",
                "end_time",
                "actual_duration",
                "updated_at",
            ]
        )

        return task
    """
    @staticmethod
    def update_status(task, user, status_value):
        allowed_choices = ["TODO", "INPROGRESS", "REVIEW", "DONE"]
        if status_value not in allowed_choices:
            raise InvalidStatusError()

        is_project_manager = ProjectRole.objects.filter(
            project=task.project,
            user=user,
            role__in=['ADMIN', 'MANAGER'],
        ).exists()

        is_assignee = task.assigned_to_id == user.id
        if not is_assignee and not is_project_manager:
            raise PermissionDeniedError()

        if task.status == "DONE" and status_value != "DONE":
            raise InvalidStatusError()

        if status_value == "INPROGRESS" and not task.start_time:
            task.start_time = timezone.now()

        if status_value == "REVIEW":
            report = TechnicalReportForm.objects.filter(
                task=task,
                user=task.assigned_to,
                status='SUBMITTED',
            ).order_by('-created_at').first()

            if not report:
                raise TechnicalReportMissingError()

            managers = User.objects.filter(
                projectrole__project=task.project,
                projectrole__role__in=['ADMIN', 'MANAGER'],
            ).distinct()
            for manager in managers:
                create_notification(
                    recipient=manager,
                    notification_type='REPORT_SUBMITTED',
                    title="New Technical Report Submitted",
                    message=f"Employee {user.get_full_name() or user.username} submitted a technical report for '{task.title}'.",
                    navigation_target=f"/task_details/{task.id}",
                )

        if status_value == "DONE":
            task.end_time = timezone.now()
            task.actual_duration = task.end_time - task.start_time if task.start_time else None

        task.status = status_value
        task.save(update_fields=["status", "start_time", "end_time", "actual_duration", "updated_at"])

        return task







    @staticmethod
    def review_technical_report(task, report, manager_user, feedback_text=None, new_status=None, quality=None):
        if new_status not in ['APPROVED', 'REJECTED']:
            raise ValidationError({"status": "Status must be APPROVED or REJECTED."})

        is_project_manager = ProjectRole.objects.filter(
            project=task.project,
            user=manager_user,
            role__in=['ADMIN', 'MANAGER'],
        ).exists()
        if not is_project_manager:
            raise PermissionDeniedError()

        now = timezone.now()

        if feedback_text:
            manager_entry = {
                "manager_name": manager_user.get_full_name() or manager_user.username,
                "note": feedback_text,
                "date": now.strftime("%Y-%m-%d %H:%M"),
            }
            current_feedbacks = report.manager_feedbacks or []
            current_feedbacks.append(manager_entry)
            report.manager_feedbacks = current_feedbacks
            report.manager_feedback = feedback_text

        if quality:
            report.quality = quality

        report.status = new_status
        report.save()

        if new_status == 'APPROVED':
            task.status = "DONE"
            task.end_time = now
            task.actual_duration = task.end_time - task.start_time if task.start_time else None

            create_notification(
                recipient=task.assigned_to,
                notification_type='SYSTEM_ALERT',
                title="Report accepted",
                message=f"Your report for task '{task.title}' was accepted.",
                navigation_target=f"/report_details/{report.id}",
            )
        else:
            task.status = "INPROGRESS"
            create_notification(
                recipient=task.assigned_to,
                notification_type='REPORT_REJECTED',
                title="Report Needs Adjustment",
                message=f"Your report for task '{task.title}' needs adjustments.",
                navigation_target=f"/report_details/{report.id}",
            )

        task.save()
        ActivityLog.objects.create(
            user=manager_user,
            action="REPORT_REVIEWED",
            action_id=report.id,
            changes={
                "subject_name": manager_user.username,
                "target_title": f"Report for {task.title}",
                "note": feedback_text,
                "status": new_status,
                "is_by_admin": True,
            },
        )

        return {
            "id": report.id,
            "status": report.status,
            "description": report.description,
            "manager_feedback": report.manager_feedback,
            "manager_feedbacks": report.manager_feedbacks,
            "task_status": task.status,
        }




    @staticmethod
    def perform_update(serializer, instance, user, status_value=None):
        if status_value == 'INPROGRESS' and not instance.start_time:
            serializer.save(start_time=timezone.now())
        elif status_value == 'DONE':
            now = timezone.now()
            actual_duration = now - instance.start_time if instance.start_time else None
            serializer.save(end_time=now, actual_duration=actual_duration)
        else:
            serializer.save()
