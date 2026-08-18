from django.db import transaction
from rest_framework.exceptions import PermissionDenied, ValidationError

from users.constants import create_activity_log
from users.models import LeaveTaskAction, Notification, ProjectRole, RequestForm, Task
from users.errors.exceptions import BaseAppException

from datetime import timedelta
from django.utils import timezone

from users.services.leave_service import LeaveRequestService

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

        project_role = ProjectRole.objects.filter(
            project=task.project,
            user=user,
        ).values_list("role", flat=True).first()

        if project_role != "EMPLOYEE" or task.assigned_to_id != user.id:
            raise PermissionDenied(
                "Only the employee assigned to this task can create its report."
            )

        if task.status != "INPROGRESS":
            raise ValidationError(
                "Reports can only be created while the task is in progress."
            )

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
        project_role = ProjectRole.objects.filter(
            project=report.task.project,
            user=user,
        ).values_list("role", flat=True).first()

        if project_role != "EMPLOYEE" or report.task.assigned_to_id != user.id:
            raise PermissionDenied(
                "Only the employee assigned to this task can update its draft report."
            )

        if report.user_id != user.id:
            raise PermissionDenied(
                "You can only update your own technical report."
            )

        if report.status != "DRAFT":
            raise ValidationError({
                "status": "Only draft reports can be updated."
            })

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
    def delete_technical_report_draft(report, user):
        project_role = ProjectRole.objects.filter(
            project=report.task.project,
            user=user,
        ).values_list("role", flat=True).first()

        if project_role != "EMPLOYEE" or report.task.assigned_to_id != user.id:
            raise PermissionDenied(
                "Only the employee assigned to this task can delete its draft report."
            )

        if report.user_id != user.id:
            raise PermissionDenied(
                "You can only delete your own technical report."
            )

        if report.status != "DRAFT":
            raise ValidationError({
                "status": "Only draft reports can be deleted."
            })

        create_activity_log(
            user=user,
            action="REPORT_DELETED",
            action_id=report.id,
            changes={
                "subject_name": user.username,
                "target_title": report.task.title,
                "reason": (
                    f"Draft report for task '{report.task.title}' "
                    f"was deleted by {user.username}."
                ),
                "is_by_admin": False,
            },
        )

        report.delete()

    @staticmethod
    def submit_technical_report(report, user):
        task = report.task


        if task.assigned_to != user:
            raise BaseAppException(
                detail="You can only submit a report for your own task.",
                code="REQUEST_UPDATE_NOT_ALLOWED",
                status_code=403,
            )

        if task.status != "INPROGRESS":
            raise BaseAppException(
                detail=(
                    "Reports can only be submitted "
                    "while the task is in progress."
                ),
                code="TASK_NOT_IN_PROGRESS",
                status_code=400,
            )

        latest_report = (
            task.technical_reports
            .exclude(id=report.id)
            .order_by("-created_at")
            .first()
        )

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

        now = timezone.now()



        if task.start_time:
            worked_duration = now - task.start_time

            task.actual_duration = (
                task.actual_duration
                or timedelta(0)
            ) + worked_duration

        task.start_time = None
        task.end_time = None

        report.duration_time = (
            task.actual_duration
            or timedelta(0)
        )

        report.status = "SUBMITTED"

        report.save(
            update_fields=[
                "status",
                "duration_time",
                "updated_at",
            ]
        )

        task.status = "REVIEW"

        task.save(
            update_fields=[
                "status",
                "actual_duration",
                "start_time",
                "end_time",
                "updated_at",
            ]
        )

        managers = (
            ProjectRole.objects
            .filter(
                project=task.project,
                role__in=[
                    "ADMIN",
                    "MANAGER",
                ],
            )
            .exclude(user=user)
            .select_related("user")
        )

        for manager_role in managers:
            Notification.objects.create(
                recipient=manager_role.user,
                notification_type="REPORT_SUBMITTED",
                title="New Technical Report Submitted",
                message=(
                    f"Employee "
                    f"{user.get_full_name() or user.username} "
                    f"has submitted a technical report "
                    f"for the task '{task.title}'."
                ),
                navigation_target=(
                    f"/task_details/{task.id}"
                ),
            )

        create_activity_log(
            user=user,
            action="REPORT_SUBMITTED",
            action_id=report.id,
            changes={
                "subject_name": user.username,
                "target_title": task.title,
                "reason": (
                    f"Report for task '{task.title}' "
                    f"was submitted by {user.username}."
                ),
                "is_by_admin": False,
            },
        )

        return report
#///////////////////////////////////////////////////////////////////////////////////////////////
class FormService:
    @staticmethod
    def create_request_form(serializer, user):
        validated_data = serializer.validated_data

        project = validated_data.get("project")
        request_type = validated_data.get("request_type")

        project_role = ProjectRole.objects.filter(
            project=project,
            user=user,
        ).first()

        if not project_role:
            raise ValidationError({
                "detail": (
                    "Only project members can create requests "
                    "for this project."
                )
            })


        if project_role.role == "ADMIN":
            raise ValidationError({
                        "request_type": [
                            "Project admins cannot create leave requests."
                        ]
                    })



        leave_start = validated_data.get("leave_start")
        leave_end = validated_data.get("leave_end")

        if not leave_start:
            raise ValidationError({
                "leave_start": [
                    "Leave start date is required."
                ]
            })

        if not leave_end:
            raise ValidationError({
                "leave_end": [
                    "Leave end date is required."
                ]
            })

        if leave_end <= leave_start:
            raise ValidationError({
                "leave_end": [
                    "Leave end date must be after leave start date."
                ]
            })

        duplicate_leave = RequestForm.objects.filter(
            user=user,
            project=project,
            request_type="LEAVE",
            status__in=[
                "PENDING",
                "ACTION_REQUIRED",
                "APPROVED",
            ],
            leave_start__lt=leave_end,
            leave_end__gt=leave_start,
        ).exists()

        if duplicate_leave:
            raise ValidationError({
                "leave_start": [
                    (
                        "You already have a pending, action-required, "
                        "or approved leave request for this period."
                    )
                ]
            })

        request_form = serializer.save(
            user=user,
            status="PENDING",
        )

        managers = ProjectRole.objects.filter(
            project=request_form.project,
            role__in=["ADMIN", "MANAGER"],
        ).exclude(
            user=user,
        ).select_related("user")

        for manager_role in managers:
            Notification.objects.create(
                recipient=manager_role.user,
                notification_type="SYSTEM_ALERT",
                title="New Request Submitted",
                message=(
                    f"{user.get_full_name() or user.username} "
                    f"submitted a new request: "
                    f"'{request_form.title}'."
                ),
                navigation_target=f"/requests/{request_form.id}",
            )

        create_activity_log(
            user=user,
            action="REQUEST_CREATED",
            action_id=request_form.id,
            changes={
                "subject_name": user.username,
                "target_title": request_form.title,
                "reason": (
                    f"Request '{request_form.title}' was created "
                    f"by {user.username} in project "
                    f"{request_form.project.name}."
                ),
                "is_by_admin": False,
            },
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
        if request_form.status not in [
                "PENDING",
                "ACTION_REQUIRED",
            ]:
            raise ValidationError(
                "Only pending requests can be deleted."
            )

        if request_form.request_type == "LEAVE":
            LeaveRequestService.rollback_leave_actions(
                leave_request=request_form,
                user=user,
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
    @transaction.atomic
    def review_request_form(
        *,
        request_form,
        manager_user,
        status_value,
        manager_feedback=None,
    ):

        allowed_current_statuses = ["PENDING", "ON_HOLD"]

        if request_form.request_type == "LEAVE":
            allowed_current_statuses.append("ACTION_REQUIRED")

        if request_form.status not in allowed_current_statuses:
            raise ValidationError({
                "status": "This request cannot be reviewed in its current status."
            })



        reviewer_role = ProjectRole.objects.filter(
            project=request_form.project,
            user=manager_user,
            role__in=["ADMIN", "MANAGER"],
        ).first()

        if not reviewer_role:
            raise PermissionDenied(
                "You are not allowed to review this request."
            )

        if (
            request_form.request_type == "LEAVE"
            and request_form.user_id == manager_user.id
        ):
            raise PermissionDenied(
                "You cannot review your own leave request."
            )

        request_owner_role = ProjectRole.objects.filter(
            project=request_form.project,
            user=request_form.user,
        ).first()

        if (
            request_form.request_type == "LEAVE"
            and request_owner_role
            and request_owner_role.role == "MANAGER"
            and reviewer_role.role != "ADMIN"
        ):
            raise PermissionDenied(
                "Only a project admin can review a manager's leave request."
            )

        if status_value not in ["APPROVED", "REJECTED", "ON_HOLD"]:
            raise ValidationError({
                "status": (
                    "Status must be APPROVED, REJECTED, or ON_HOLD."
                )
            })

        if request_form.request_type == "LEAVE":
            FormService._validate_leave_review(
                request_form=request_form,
                status_value=status_value,
            )
        if (
            request_form.request_type == "LEAVE"
            and status_value == "REJECTED"
        ):
            LeaveRequestService.rollback_leave_actions(
                leave_request=request_form,
                user=manager_user,
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

        if request_form.user_id != manager_user.id:
            Notification.objects.create(
                recipient=request_form.user,
                notification_type="SYSTEM_ALERT",
                title="Request Reviewed",
                message=(
                    f"Your request '{request_form.title}' "
                    f"has been {status_value.lower()}."
                ),
                navigation_target=f"/requests/{request_form.id}",
            )

        create_activity_log(
            user=manager_user,
            action="REQUEST_REVIEWED",
            action_id=request_form.id,
            changes={
                "subject_name": manager_user.username,
                "target_title": request_form.title,
                "reason": (
                    f"Request '{request_form.title}' was "
                    f"{status_value.lower()} by "
                    f"{manager_user.username} in project "
                    f"{request_form.project.name}."
                ),
                "is_by_admin": True,
            },
        )

        return request_form

    @staticmethod
    def _validate_leave_review(
        *,
        request_form,
        status_value,
    ):
        if status_value not in ["APPROVED", "REJECTED"]:
            return

        has_active_tasks = Task.objects.filter(
            project=request_form.project,
            assigned_to=request_form.user,
            is_deleted=False,
            is_archived=False,
        ).exists()

        analysis_exists = LeaveTaskAction.objects.filter(
            request=request_form,
        ).exists()

        if has_active_tasks and not analysis_exists:
            raise ValidationError({
                "leave_analysis": (
                    "Leave impact must be analyzed before "
                    "approving or rejecting this request."
                )
            })

        if status_value != "APPROVED":
            return

        unresolved_actions_exist = LeaveTaskAction.objects.filter(
            request=request_form,
            requires_action=True,
            is_resolved=False,
        ).exists()

        if unresolved_actions_exist:
            raise ValidationError({
                "leave_actions": (
                    "All affected tasks must be resolved "
                    "before approving the leave request."
                )
            })










































