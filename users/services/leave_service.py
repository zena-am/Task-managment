
from datetime import timedelta

from django.db import transaction
from django.utils import timezone
from rest_framework.exceptions import PermissionDenied, ValidationError

from users.models import LeaveTaskAction, ProjectRole, Task
from users.services.task_service import TaskService

class LeaveRequestService:
    @staticmethod
    @transaction.atomic
    def analyze_leave_impact(
        *,
        leave_request,
        manager_user,
    ):
        if leave_request.request_type != "LEAVE":
            raise ValidationError({
                "request_type": (
                    "Leave impact analysis is only available "
                    "for leave requests."
                )
            })

        if leave_request.user_id == manager_user.id:
            raise PermissionDenied(
                "You cannot analyze your own leave request."
            )

        is_manager = ProjectRole.objects.filter(
            project=leave_request.project,
            user=manager_user,
            role__in=["ADMIN", "MANAGER"],
        ).exists()


        if not is_manager:
            raise PermissionDenied(
                "You are not allowed to analyze this leave request."
            )

        if not leave_request.leave_start:
            raise ValidationError({
                "leave_start": "Leave start is required."
            })

        if not leave_request.leave_end:
            raise ValidationError({
                "leave_end": "Leave end is required."
            })

        if leave_request.leave_end <= leave_request.leave_start:
            raise ValidationError({
                "leave_end": (
                    "Leave end must be later than leave start."
                )
            })

        if leave_request.status in ["APPROVED", "REJECTED"]:
            raise ValidationError({
                "status": (
                    "An approved or rejected leave request "
                    "cannot be analyzed."
                )
            })

        tasks = Task.objects.filter(
            project=leave_request.project,
            assigned_to=leave_request.user,
            is_deleted=False,
            is_archived=False,
        ).select_related(
            "assigned_to",
            "project",
        ).order_by("due_date")

        results = []

        for task in tasks:
            analysis = LeaveRequestService.analyze_task_for_leave(
                task=task,
                leave_request=leave_request,
            )

            leave_action, created = (
                LeaveTaskAction.objects.update_or_create(
                    request=leave_request,
                    task=task,
                    defaults={
                        "impact": analysis["impact"],
                        "requires_action": analysis[
                            "requires_action"
                        ],
                    },
                )
            )

            if analysis["requires_action"]:
                if created or leave_action.action == "NO_ACTION":
                    leave_action.action = None
                    leave_action.is_resolved = False
                    leave_action.resolved_by = None
                    leave_action.resolved_at = None
                    leave_action.new_assignee = None
                    leave_action.new_due_date = None

            else:
                leave_action.action = "NO_ACTION"
                leave_action.is_resolved = True
                leave_action.resolved_by = manager_user
                leave_action.resolved_at = timezone.now()
                leave_action.new_assignee = None
                leave_action.new_due_date = None

            leave_action.save(
                update_fields=[
                    "action",
                    "impact",
                    "requires_action",
                    "is_resolved",
                    "resolved_by",
                    "resolved_at",
                    "new_assignee",
                    "new_due_date",
                    "updated_at",
                ]
            )

            results.append({
                "leave_task_action_id": leave_action.id,
                "task_id": task.id,
                "title": task.title,
                "status": task.status,
                "due_date": task.due_date,
                "expected_duration": task.expected_duration,
                "actual_duration": task.actual_duration,
                "remaining_duration": analysis[
                    "remaining_duration"
                ],
                "available_duration": analysis[
                    "available_duration"
                ],
                "impact": analysis["impact"],
                "requires_action": analysis[
                    "requires_action"
                ],
                "is_resolved": leave_action.is_resolved,
                "action": leave_action.action,
                "message": analysis["message"],
            })

        unresolved_actions_count = (
            LeaveTaskAction.objects.filter(
                request=leave_request,
                requires_action=True,
                is_resolved=False,
            ).count()
        )

        if unresolved_actions_count > 0:
            leave_request.status = "ACTION_REQUIRED"
        else:
            leave_request.status = "PENDING"

        leave_request.save(
            update_fields=[
                "status",
                "updated_at",
            ]
        )

        completed_tasks = sum(
            1
            for item in results
            if item["impact"] == "COMPLETED"
        )

        safe_tasks = sum(
            1
            for item in results
            if not item["requires_action"]
            and item["impact"] != "COMPLETED"
        )

        return {
            "request_id": leave_request.id,
            "employee": {
                "id": leave_request.user_id,
                "name": (
                    leave_request.user.get_full_name()
                    or leave_request.user.username
                ),
            },
            "leave_start": leave_request.leave_start,
            "leave_end": leave_request.leave_end,
            "status": leave_request.status,
            "summary": {
                "total_tasks": len(results),
                "completed_tasks": completed_tasks,
                "safe_tasks": safe_tasks,
                "tasks_requiring_action": (
                    unresolved_actions_count
                ),
            },
            "tasks": results,
        }



























    @staticmethod
    def analyze_task_for_leave(
        *,
        task,
        leave_request,
    ):
        now = timezone.now()

        expected = (
            task.expected_duration
            or timedelta(0)
        )

        actual = (
            task.actual_duration
            or timedelta(0)
        )

        remaining = expected - actual

        if remaining < timedelta(0):
            remaining = timedelta(0)

        result = {
            "impact": None,
            "requires_action": False,
            "remaining_duration": remaining,
            "available_duration": None,
            "message": "",
        }

        if task.status == "DONE":
            result.update({
                "impact": "COMPLETED",
                "requires_action": False,
                "message": "Task is already completed.",
            })

            return result
        if task.status == "REVIEW":
            result.update({
                "impact": "AWAITING_MANAGER_REVIEW",
                "requires_action": True,
                "message": (
                    "The task report must be reviewed before "
                    "the leave request can be approved."
                ),
            })
            return result


        if task.due_date < leave_request.leave_start:
            available_before_leave = max(
                leave_request.leave_start - now,
                timedelta(0),
            )

            can_finish = (
                remaining <= available_before_leave
            )

            result.update({
                "impact": (
                    "CAN_FINISH_BEFORE_LEAVE"
                    if can_finish
                    else "NOT_ENOUGH_TIME_BEFORE_LEAVE"
                ),
                "requires_action": not can_finish,
                "available_duration": (
                    available_before_leave
                ),
                "message": (
                    "Task can be completed before leave."
                    if can_finish
                    else (
                        "There is not enough time "
                        "before leave."
                    )
                ),
            })

            return result

        if (
            leave_request.leave_start
            <= task.due_date
            <= leave_request.leave_end
        ):
            result.update({
                "impact": "DUE_DURING_LEAVE",
                "requires_action": True,
                "message": (
                    "Task is due during the leave period."
                ),
            })

            return result

        available_after_leave = max(
            task.due_date - leave_request.leave_end,
            timedelta(0),
        )

        can_finish_after_return = (
            remaining <= available_after_leave
        )

        result.update({
            "impact": (
                "CAN_FINISH_AFTER_RETURN"
                if can_finish_after_return
                else "NOT_ENOUGH_TIME_AFTER_RETURN"
            ),
            "requires_action": (
                not can_finish_after_return
            ),
            "available_duration": (
                available_after_leave
            ),
            "message": (
                "Task can be completed after returning "
                "from leave."
                if can_finish_after_return
                else (
                    "There is not enough time after "
                    "returning from leave."
                )
            ),
        })

        return result






















    @staticmethod
    @transaction.atomic
    def resolve_task_action(
        *,
        leave_action,
        manager_user,
        validated_data,
    ):
        task = leave_action.task
        action = validated_data["action"]
        leave_request = leave_action.request

        if leave_request.user_id == manager_user.id:
            raise PermissionDenied(
                "You cannot resolve actions for your own leave request."
            )
        reviewer_role = ProjectRole.objects.filter(
            project=task.project,
            user=manager_user,
            role__in=["ADMIN", "MANAGER"],
        ).first()

        if not reviewer_role:
            raise PermissionDenied(
                "You are not allowed to resolve this leave task action."
            )

        request_owner_role = ProjectRole.objects.filter(
            project=task.project,
            user=leave_request.user,
        ).first()

        if (
            request_owner_role
            and request_owner_role.role == "MANAGER"
            and reviewer_role.role != "ADMIN"
        ):
            raise PermissionDenied(
                "Only a project admin can resolve actions "
                "for a manager's leave request."
            )
        task = leave_action.task
        action = validated_data["action"]

        if leave_action.is_resolved:
            raise ValidationError({
                        "action": "This leave task action is already resolved."
                    })
        valid_actions = {
            choice[0]
            for choice in LeaveTaskAction.ACTION_CHOICES
        }

        if action not in valid_actions:
            raise ValidationError({
                "action": "Invalid task action."
            })
        if leave_action.requires_action and action == "NO_ACTION":
            raise ValidationError({
                "action": (
                    "This task requires an action and cannot "
                    "be resolved using NO_ACTION."
                )
            })
        if task.status == "DONE":
            raise ValidationError({
                "task": "Completed tasks cannot be modified."
            })

        if action == "TRANSFER_TASK":
            LeaveRequestService._transfer_task(
                leave_action=leave_action,
                task=task,
                manager_user=manager_user,
                new_assignee=validated_data.get("new_assignee"),
            )

        elif action == "EXTEND_DUE_DATE":
            LeaveRequestService._extend_task_due_date(
                leave_action=leave_action,
                task=task,
                new_due_date=validated_data.get("new_due_date"),
            )

        elif action == "PAUSE_TASK":
            LeaveRequestService._pause_task(
                leave_action=leave_action,
                task=task,
            )

        elif action == "NO_ACTION":
            LeaveRequestService._take_no_action(
                leave_action=leave_action,
            )


        else:
            raise ValidationError({
                "action": "Invalid task action."
            })

        leave_action.action = action
        leave_action.is_resolved = True
        leave_action.resolved_by = manager_user
        leave_action.resolved_at = timezone.now()

        leave_action.save(
            update_fields=[
                "action",
                "new_assignee",
                "new_due_date",
                "is_resolved",
                "resolved_by",
                "resolved_at",
                "updated_at",
                "previous_assignee",
                "previous_due_date",
                "previous_task_status",
            ]
        )

        return leave_action













    @staticmethod
    @transaction.atomic
    def rollback_leave_actions(*, leave_request, user):

        leave_actions = (
            LeaveTaskAction.objects
            .select_for_update()
            .filter(
                request=leave_request,
                is_resolved=True,
            )
            .select_related(
                "task",
                "previous_assignee",
                "new_assignee",
            )
            .order_by("-resolved_at")
        )

        for leave_action in leave_actions:
            task = leave_action.task

            if leave_action.action == "TRANSFER_TASK":

                if (
                    leave_action.new_assignee_id
                    and task.assigned_to_id
                    != leave_action.new_assignee_id
                ):
                    raise ValidationError({
                        "detail": (
                            f"Task '{task.title}' was reassigned after "
                            "the leave action and cannot be restored automatically."
                        ),
                        "code": "TASK_CHANGED_AFTER_LEAVE_ACTION",
                        "task_id": task.id,
                    })

                task.assigned_to = leave_action.previous_assignee

                task.save(
                    update_fields=[
                        "assigned_to",
                        "updated_at",
                    ]
                )

            elif leave_action.action == "EXTEND_DUE_DATE":

                if (
                    leave_action.new_due_date
                    and task.due_date != leave_action.new_due_date
                ):
                    raise ValidationError({
                        "detail": (
                            f"The due date of task '{task.title}' "
                            "was changed after the leave action."
                        ),
                        "code": "TASK_CHANGED_AFTER_LEAVE_ACTION",
                        "task_id": task.id,
                    })

                task.due_date = leave_action.previous_due_date

                task.save(
                    update_fields=[
                        "due_date",
                        "updated_at",
                    ]
                )

            elif leave_action.action == "PAUSE_TASK":

                if task.status != "PAUSED":
                    raise ValidationError({
                        "detail": (
                            f"Task '{task.title}' status was changed "
                            "after the leave action."
                        ),
                        "code": "TASK_CHANGED_AFTER_LEAVE_ACTION",
                        "task_id": task.id,
                    })

                task.status = (
                    leave_action.previous_task_status
                    or "TODO"
                )

                task.save(
                    update_fields=[
                        "status",
                        "updated_at",
                    ]
                )

            leave_action.delete()







    @staticmethod
    @transaction.atomic
    def return_from_leave(
        *,
        leave_request,
        user,
    ):
        if leave_request.user_id != user.id:
            raise PermissionDenied(
                "You can only return from your own leave."
            )

        if leave_request.request_type != "LEAVE":
            raise ValidationError({
                "request_type": (
                    "This operation is only available "
                    "for leave requests."
                )
            })

        if leave_request.status != "APPROVED":
            raise ValidationError({
                "status": (
                    "Only approved leave requests can "
                    "be completed."
                )
            })

        now = timezone.now()

        leave_actions = (
            LeaveTaskAction.objects
            .select_for_update()
            .filter(
                request=leave_request,
                action="PAUSE_TASK",
                is_resolved=True,
            )
            .select_related("task")
        )

        resumed_tasks = []

        for leave_action in leave_actions:
            task = leave_action.task

            if task.is_deleted or task.is_archived:
                continue

            if task.status != "PAUSED":
                continue

            previous_status = (
                leave_action.previous_task_status
                or "TODO"
            )

            if previous_status == "DONE":
                previous_status = "TODO"

            if (
                previous_status == "INPROGRESS"
                and task.is_blocked
            ):
                previous_status = "TODO"

            task.status = previous_status

            task.save(
                update_fields=[
                    "status",
                    "updated_at",
                ]
            )

            resumed_tasks.append({
                "task_id": task.id,
                "title": task.title,
                "status": task.status,
                "is_blocked": task.is_blocked,
            })

        leave_request.status = "COMPLETED"
        leave_request.actual_return_at = now

        leave_request.save(
            update_fields=[
                "status",
                "actual_return_at",
                "updated_at",
            ]
        )

        return {
            "request_id": leave_request.id,
            "status": leave_request.status,
            "actual_return_at": leave_request.actual_return_at,
            "resumed_tasks": resumed_tasks,
        }















    @staticmethod
    def _transfer_task(
        *,
        leave_action,
        task,
        manager_user,
        new_assignee,
    ):
        if not new_assignee:
            raise ValidationError({
                "new_assignee": "New assignee is required."
            })
        if leave_action.request.user_id == new_assignee.id:
            raise ValidationError({
                "new_assignee": (
                    "The task cannot be transferred to the employee "
                    "who is taking leave."
                )
            })

        if task.assigned_to_id == new_assignee.id:
            raise ValidationError({
                "new_assignee": (
                    "The new assignee must be different "
                    "from the current assignee."
                )
            })
        leave_action.previous_assignee = task.assigned_to
        TaskService.assign_task_to_user(
            task=task,
            new_assignee=new_assignee,
            performed_by=manager_user,
            project=task.project,
        )

        leave_action.new_assignee = new_assignee
        leave_action.new_due_date = None




    @staticmethod
    def _extend_task_due_date(
        *,
        leave_action,
        task,
        new_due_date,
    ):
        if not new_due_date:
            raise ValidationError({
                "new_due_date": "New due date is required."
            })
        if new_due_date <= timezone.now():
            raise ValidationError({
                "new_due_date": (
                    "The new due date must be in the future."
                )
            })
        if task.due_date and new_due_date <= task.due_date:
            raise ValidationError({
                "new_due_date": (
                    "The new due date must be later "
                    "than the current due date."
                )
            })

        if task.due_date and new_due_date <= task.due_date:
            raise ValidationError({
                "new_due_date": (
                    "The new due date must be later "
                    "than the current due date."
                )
            })
        leave_action.previous_due_date = task.due_date

        task.due_date = new_due_date


        task.save(
            update_fields=[
                "due_date",
                "updated_at",
            ]
        )

        leave_action.new_due_date = new_due_date
        leave_action.new_assignee = None


    @staticmethod
    def _pause_task(
        *,
        leave_action,
        task,
    ):
        if task.status == "PAUSED":
            raise ValidationError({
                "task": "Task is already paused."
            })

        leave_action.previous_task_status = task.status
        leave_action.new_assignee = None
        leave_action.new_due_date = None

        task.status = "PAUSED"

        task.save(
            update_fields=[
                "status",
                "updated_at",
            ]
        )


    @staticmethod
    def _take_no_action(
        *,
        leave_action,
    ):
        leave_action.new_assignee = None
        leave_action.new_due_date = None
        leave_action.previous_task_status = None