from django.utils import timezone
from users.constants import create_notification
from users.models import ActivityLog, Invitation, Notification, ProjectRole, TechnicalReportForm
from users.errors.exceptions import (
TaskAlreadyAssigned, InvalidStatusError, PermissionDeniedError, TechnicalReportMissingError)
from rest_framework import serializers
from django.utils import timezone
from users.models import Task, Notification, ActivityLog
from users.services.invitationsMemberService import InvitationService
from ..models import ProjectRole, TechnicalReportForm, User

class TaskService:

    @staticmethod
    def claim_task(task, user):
        if task.assigned_to is not None:
            raise TaskAlreadyAssigned()
        task.assigned_to = user
        task.status = "TODO"
        task.save()
        managers = User.objects.filter(
            projectrole__project=task.project,
            projectrole__role='MANAGER')

        for manager in managers:
            create_notification(
                recipient=manager,
                notification_type="TASK_CLAIMED",
                title="تم استلام مهمة",
                message=f"قام الموظف {user.username} باستلام المهمة: {task.title}",
                navigation_target=f"/tasks/{task.id}"
            )

        return task
    @staticmethod
    def create_task(user, serializer):

        assigned_user = serializer.validated_data.get('assigned_to')
        project = serializer.validated_data.get('project')

        if assigned_user is not None:
            initial_status = 'TODO'
        else:
            initial_status = 'UNASSIGNED'
        task = serializer.save(creator=user,status=initial_status)


        is_project_member = True
        if assigned_user:
            is_project_member = ProjectRole.objects.filter(project=project,user=assigned_user).exists()
            create_notification(
            recipient=assigned_user,
            notification_type="TASK_ASSIGNED",
            title="مهمة جديدة",
            message=f"قام {user.username} بإسناد مهمة جديدة لك: {task.title}",
            navigation_target=f"/tasks/{task.id}")

            if not is_project_member:
                InvitationService.send_project_invitation(
                    sender=user,
                    data={
                        "project_id": task.project.id,
                        "member_emails": [assigned_user.email],
                        "role": "EMPLOYEE"
                    }
                )


        return task




    @staticmethod
    def update_status(task, user, status_value):

        allowed_choices = ["TODO", "INPROGRESS", "REVIEW"]

        if status_value not in allowed_choices:
            raise InvalidStatusError()

        if task.status == "DONE" and status_value in ["TODO", "INPROGRESS"]:
            raise InvalidStatusError()

        is_project_admin = ProjectRole.objects.filter(
            project=task.project,
            user=user,
            role='ADMIN'
        ).exists()
        """
        if user != task.assigned_to and user !=  task.supervisors.filter(id=user.id).exists() and not is_project_admin:
            raise PermissionDeniedError()
            """
        # is_supervisor = task.supervisors.filter(id=user.id).exists()

        if user != task.assigned_to  and not is_project_admin:
            raise PermissionDeniedError()

        if status_value == "INPROGRESS" and not task.start_time:
            task.start_time = timezone.now()


        if status_value == "REVIEW":
            report = TechnicalReportForm.objects.filter(
                task=task,
                user=task.assigned_to,
                status='SUBMITTED'
            ).order_by('-created_at').first()

            if not report:
                raise TechnicalReportMissingError("Employee must submit a technical report before review.")


            for supervisor in task.supervisors.all():
                Notification.objects.create(
                    recipient=supervisor,
                    notification_type='REPORT_SUBMITTED',
                    title="New Technical Report Submitted",
                    message=f"Employee {user.get_full_name() or user.username} has submitted a technical report for the task '{task.title}'.",
                    navigation_target=f"/task_details/{task.id}"
                )

            task.status = status_value
            task.save()

            return task


    @staticmethod
    def review_technical_report(task, report, manager_user, feedback_text=None, new_status=None, quality=None):
        now = timezone.now()
        manager_entry = None

        if feedback_text:
            manager_entry = {
                "manager_name": manager_user.get_full_name() or manager_user.username,
                "note": feedback_text,
                "date": now.strftime("%Y-%m-%d %H:%M")
            }
            current_feedbacks = report.manager_feedbacks or []
            current_feedbacks.append(manager_entry)
            report.manager_feedbacks = current_feedbacks
            report.manager_feedback = feedback_text
        if quality:
            report.quality = quality

            report.status = new_status
            report.save()
        else:
            manager_entry = None

        report.status = new_status
        report.save()

        if new_status == 'APPROVED':
            task.status = "DONE"
            task.end_time = now
            task.actual_duration = task.end_time - task.start_time if task.start_time else None

            Notification.objects.create(
                recipient=task.assigned_to,
                notification_type='REPORT_Approved',
                title="Report accepted",
                message=f"Your report for task '{task.title}' was reviewed by {manager_user.get_full_name()} and accepted.",
                navigation_target=f"/report_details/{report.id}"
            )

            ActivityLog.objects.create(
                user=task.assigned_to,
                action="REPORT_REVIEWED",
                action_id=report.id,
                changes={
                    "subject_name": manager_user.username,
                    "target_title": f"Report for {task.title}",
                    "note": feedback_text,
                    "is_by_admin": True
                }
            )

        elif new_status == 'REJECTED':
            task.status = "INPROGRESS"
            Notification.objects.create(
                recipient=task.assigned_to,
                notification_type='REPORT_REJECTED',
                title="Report Needs Adjustment",
                message=f"Your report for task '{task.title}' was reviewed by {manager_user.get_full_name()} and needs adjustments.",
                navigation_target=f"/report_details/{report.id}"
            )

            ActivityLog.objects.create(
                user=task.assigned_to,
                action="REPORT_REVIEWED",
                action_id=report.id,
                changes={
                    "subject_name": manager_user.username,
                    "target_title": f"Report for {task.title}",
                    "note": feedback_text,
                    "is_by_admin": True
                }
            )

        task.save()

        return {
            "id": report.id,
            "status": report.status,
            "description": report.description,
            "manager_feedbacks": report.manager_feedbacks
        }



    def perform_create(self, serializer):
        assigned_to_user = serializer.validated_data.get('assigned_to')

        if assigned_to_user is not None:
            initial_status = 'TODO'
        else:
            initial_status = 'UNASSIGNED'

        task =  serializer.save(
            user=self.request.user,
            status=initial_status
        )

        task.supervisors.add(self.request.user)

        return task

    def perform_update(serializer, instance, user, status_value):
        #status = user.requests.data.get('status')
        # instance = user.get_object()
        if status_value == 'INPROGRESS' and not instance.start_time:
            serializer.save(start_time=timezone.now())
        elif status_value == 'REVIEW':
            now = timezone.now()
            actual_dur = now - instance.start_time if instance.start_time else None
            serializer.save(end_time=now, actual_duration=actual_dur)
        else:
            serializer.save()
