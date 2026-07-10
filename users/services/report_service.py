from rest_framework.exceptions import PermissionDenied, ValidationError

from users.constants import create_activity_log
from users.models import Notification, ProjectRole
from users.errors.exceptions import BaseAppException



class ReportService:

    @staticmethod
    def update_technical_report(report, serializer, user):
        report = serializer.save()

        create_activity_log(
            user=user,
            action="REPORT_DRAFT_UPDATED",
            action_id=report.id,
            changes={
                "subject_name": user.username,
                "target_title": report.task.title,
                "reason": f"Report for task '{report.task.title}' was updated by {user.username}.",
                "is_by_admin": False
            }
        )

        return report

    @staticmethod
    def delete_technical_report(report, user):
        create_activity_log(
            user=user,
            action="REPORT_DELETED",
            action_id=report.id,
            changes={
                "subject_name": user.username,
                "target_title": report.task.title,
                "reason": f"Report for task '{report.task.title}' was deleted by {user.username}.",
                "is_by_admin": False
            }
        )

        report.delete()
    @staticmethod
    def save_technical_report_draft(serializer, user):
        task = serializer.validated_data.get("task")

        latest_report = task.technical_reports.order_by("-created_at").first()

        if latest_report:
            if latest_report.status == "SUBMITTED":

                raise BaseAppException(
                detail="A submitted report is already awaiting manager review.",
                code="REPORT_ALREADY_SUBMITTED",
                status_code=400)

            if latest_report.status == "APPROVED":
                raise BaseAppException(
            detail="This task already has an approved report.",
            code="REPORT_ALREADY_APPROVED",
            status_code=400
)

            if latest_report.status == "DRAFT":
                raise BaseAppException(
    detail="A draft report already exists for this task.",
    code="REPORT_DRAFT_ALREADY_EXISTS",
    status_code=400
)

        report = serializer.save(
            user=user,
            status="DRAFT"
        )

        create_activity_log(
            user=user,
            action="REPORT_DRAFT_CREATED",
            action_id=report.id,
            changes={
                "subject_name": user.username,
                "target_title": task.title,
                "reason": f"Draft report for task '{task.title}' was created by {user.username}.",
                "is_by_admin": False
            }
        )
        return report

    @staticmethod
    def update_technical_report_draft(report, serializer, user):
        report = serializer.save()

        create_activity_log(
            user=user,
            action="REPORT_DRAFT_UPDATED",
            action_id=report.id,
            changes={
                "subject_name": user.username,
                "target_title": report.task.title,
                "reason": f"Draft report for task '{report.task.title}' was updated by {user.username}.",
                "is_by_admin": False
            }
        )

        return report


    @staticmethod
    def submit_technical_report(report, user):
        task = report.task

        if task.assigned_to != user:
            raise BaseAppException(
    detail="You can only update your own request.",
    code="REQUEST_UPDATE_NOT_ALLOWED",
    status_code=403
)

        if task.status != "INPROGRESS":
            raise BaseAppException(
    detail="Reports can only be submitted while the task is in progress.",
    code="TASK_NOT_IN_PROGRESS",
    status_code=400
)
        latest_report = task.technical_reports.exclude(id=report.id).order_by("-created_at").first()

        if latest_report:
            if latest_report.status == "SUBMITTED":
                raise ValidationError(
                    "A report is already awaiting manager review."
                )

            if latest_report.status == "APPROVED":
                raise ValidationError(
                    "This task already has an approved report."
                )
        if not report.description:
            raise ValidationError(
                "Description is required before submitting the report."
            )

        report.status = "SUBMITTED"
        report.save(update_fields=["status", "updated_at"])

        task.status = "REVIEW"
        task.save(update_fields=["status", "updated_at"])

        managers = ProjectRole.objects.filter(
            project=task.project,
            role__in=["ADMIN", "MANAGER"]
        ).select_related("user")

        for manager_role in managers:
            Notification.objects.create(
                recipient=manager_role.user,
                notification_type="REPORT_SUBMITTED",
                title="New Technical Report Submitted",
                message=(
                    f"Employee {user.get_full_name() or user.username} "
                    f"has submitted a technical report for the task '{task.title}'."
                ),
                navigation_target=f"/task_details/{task.id}"
            )

        create_activity_log(
            user=user,
            action="REPORT_SUBMITTED",
            action_id=report.id,
            changes={
                "subject_name": user.username,
                "target_title": task.title,
                "reason": f"Report for task '{task.title}' was submitted by {user.username}.",
                "is_by_admin": False
            }
        )

        return report

#///////////////////////////////////////////////////////////////////////////////////////////////
class FormService:

    @staticmethod
    def create_request_form(serializer, user):
        request_form = serializer.save(
            user=user,
            status="PENDING"
        )

        managers = ProjectRole.objects.filter(project=request_form.project,role__in=["ADMIN", "MANAGER"]).exclude(user=user).select_related("user")

        for manager_role in managers:
            Notification.objects.create(
                recipient=manager_role.user,
                notification_type="SYSTEM_ALERT",
                title="New Request Submitted",
                message=(
                    f"{user.get_full_name() or user.username} "
                    f"submitted a new request: '{request_form.title}'."),
                navigation_target=f"/requests/{request_form.id}"
            )

        create_activity_log(
            user=user,
            action="REQUEST_CREATED",
            action_id=request_form.id,
            changes={
                "subject_name": user.username,
                "target_title": request_form.title,
                "reason": f"Request '{request_form.title}' was created by {user.username} in project {request_form.project.name}.",
                "is_by_admin": False
            }
        )
        return request_form
    @staticmethod
    def update_request_form(request_form, serializer, user):
        if request_form.user != user:
            raise PermissionDenied(
                "You can only update your own request."
            )

        if request_form.status != "PENDING":
            raise ValidationError(
                "Only pending requests can be updated."
            )
        request_form = serializer.save()

        create_activity_log(
            user=user,
            action="REQUEST_UPDATED",
            action_id=request_form.id,
            changes={
                "subject_name": user.username,
                "target_title": request_form.title,
                "reason": f"Request '{request_form.title}' was updated by {user.username} in project {request_form.project.name}.",
                "is_by_admin": False
            }
        )

        return request_form

    @staticmethod
    def delete_request_form(request_form, user):
        if request_form.user != user:
            raise PermissionDenied(
                "You can only delete your own request."
            )

        if request_form.status != "PENDING":
            raise ValidationError(
                "Only pending requests can be deleted."
            )
        request_id = request_form.id
        request_title = request_form.title
        project_name = request_form.project.name

        create_activity_log(
            user=user,
            action="REQUEST_DELETED",
            action_id=request_id,
            changes={
                "subject_name": user.username,
                "target_title": request_title,
                "reason": f"Request '{request_title}' was deleted by {user.username} in project {project_name}.",
                "is_by_admin": False
            }
        )
        request_form.delete()

    @staticmethod
    def review_request_form(request_form, manager_user, status_value, manager_feedback=None):
        is_manager = ProjectRole.objects.filter(project=request_form.project,user=manager_user,role__in=["ADMIN", "MANAGER"]).exists()
        if not is_manager:
            raise PermissionDenied("You are not allowed to review this request.")

        if request_form.status != "PENDING":
            raise ValidationError(
                "Only pending requests can be reviewed."
            )

        if status_value not in ["APPROVED", "REJECTED"]:
            raise ValidationError(
                "Status must be APPROVED or REJECTED."
            )

        request_form.status = status_value

        if manager_feedback is not None:
            request_form.manager_feedback = manager_feedback

        request_form.save(
            update_fields=[
                "status",
                "manager_feedback",
                "updated_at",
            ]
        )

        Notification.objects.create(
            recipient=request_form.user,
            notification_type="SYSTEM_ALERT",
            title="Request Reviewed",
            message=(
                f"Your request '{request_form.title}' "
                f"has been {status_value.lower()}."
            ),
            navigation_target=f"/requests/{request_form.id}"
        )

        create_activity_log(
            user=manager_user,
            action="REQUEST_REVIEWED",
            action_id=request_form.id,
            changes={
                "subject_name": manager_user.username,
                "target_title": request_form.title,
                "reason": f"Request '{request_form.title}' was {status_value.lower()} by {manager_user.username} in project {request_form.project.name}.",
                "is_by_admin": True
            }
        )

        return request_form