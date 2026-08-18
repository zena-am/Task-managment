from datetime import timedelta
from django.db import transaction
from django.utils import timezone
from rest_framework.exceptions import PermissionDenied, ValidationError
from users.models import LeaveTaskAction, ProjectRole, Task
from users.services.task_service import TaskService
from users.services.task_transfer_service import TaskTransferService
from users.services.working_time_service import WorkingTimeService

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

        reviewer_role = ProjectRole.objects.filter(
            project=leave_request.project,
            user=manager_user,
            role__in=["ADMIN", "MANAGER"],
        ).first()

        if not reviewer_role:
            raise PermissionDenied(
                "You are not allowed to analyze this leave request."
            )

        request_owner_role = ProjectRole.objects.filter(
            project=leave_request.project,
            user=leave_request.user,
        ).first()

        if (
            request_owner_role
            and request_owner_role.role == "MANAGER"
            and reviewer_role.role != "ADMIN"
        ):
            raise PermissionDenied(
                "Only a project admin can analyze a manager's leave request."
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

        if (
            task.status == "INPROGRESS"
            and task.start_time
        ):
            current_session = (
                now - task.start_time
            )

            actual += current_session

        remaining = (
            expected - actual
        )

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
                "message": (
                    "Task is already completed."
                ),
            })

            return result

        if task.status == "REVIEW":
            result.update({
                "impact": (
                    "AWAITING_MANAGER_REVIEW"
                ),
                "requires_action": True,
                "message": (
                    "The task report must be reviewed "
                    "before the leave request can "
                    "be approved."
                ),
            })

            return result


        if (
            task.due_date
            < leave_request.leave_start
        ):
            available_before_leave_hours = (
    WorkingTimeService.get_working_hours_between(
        workspace=task.project.workspace,
        start_datetime=now,
        end_datetime=leave_request.leave_start,
    )
)

            remaining_hours = (
                remaining.total_seconds() / 3600
            )

            can_finish = (
                remaining_hours <= available_before_leave_hours
            )

            result.update({
                "impact": (
                    "CAN_FINISH_BEFORE_LEAVE"
                    if can_finish
                    else (
                        "NOT_ENOUGH_TIME_BEFORE_LEAVE"
                    )
                ),
                "requires_action": (
                    not can_finish
                ),
                "available_duration": (
                available_before_leave_hours                ),
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
                    "Task is due during the "
                    "leave period."
                ),
            })

            return result


        available_after_leave_hours = (
            WorkingTimeService.get_working_hours_between(
                workspace=task.project.workspace,
                start_datetime=leave_request.leave_end,
                end_datetime=task.due_date,
            )
        )

        remaining_hours = (
            remaining.total_seconds()
            / 3600
        )

        can_finish_after_return = (
            remaining_hours
            <= available_after_leave_hours
)

        result.update({
            "impact": (
                "CAN_FINISH_AFTER_RETURN"
                if can_finish_after_return
                else (
                    "NOT_ENOUGH_TIME_AFTER_RETURN"
                )
            ),
            "requires_action": (
                not can_finish_after_return
            ),
            "available_duration": (
                available_after_leave_hours
            ),
            "message": (
                "Task can be completed after "
                "returning from leave."
                if can_finish_after_return
                else (
                    "There is not enough time "
                    "after returning from leave."
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
            new_due_date=validated_data.get(
                "new_due_date"
            ),
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
                            f"Task '{task.title}' was reassigned "
                            f"after the leave action and cannot "
                            f"be restored automatically."
                        ),
                        "code": (
                            "TASK_CHANGED_AFTER_LEAVE_ACTION"
                        ),
                        "task_id": task.id,
                    })


                task.assigned_to = (
                    leave_action.previous_assignee
                )

                task.assignment_state = (
                    "ASSIGNED"
                    if task.assigned_to_id
                    else "UNASSIGNED_RETURNED"
                )

                task.due_date = (
                    leave_action.previous_due_date
                )


                previous_status = (
                    leave_action.previous_task_status
                    or "TODO"
                )

                if (
                    previous_status == "INPROGRESS"
                    and task.is_blocked
                ):

                    task.status = "TODO"
                    task.start_time = None

                elif previous_status == "INPROGRESS":
                    task.status = "INPROGRESS"


                    task.start_time = timezone.now()

                else:
                    task.status = previous_status
                    task.start_time = None

                task.end_time = None

                task.save(
                    update_fields=[
                        "assigned_to",
                        "assignment_state",
                        "status",
                        "due_date",
                        "start_time",
                        "end_time",
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

                TaskService.validate_dependency_due_date(
                task=task,
                new_due_date=(
                    leave_action.previous_due_date
                ),
            )
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

                previous_status = (
                    leave_action.previous_task_status
                    or "TODO"
                )

                task.due_date = (
                    leave_action.previous_due_date
                )

                if (
                    previous_status == "INPROGRESS"
                    and not task.is_blocked
                ):
                    task.status = "INPROGRESS"
                    task.start_time = timezone.now()

                elif (
                    previous_status == "INPROGRESS"
                    and task.is_blocked
                ):
                    task.status = "TODO"
                    task.start_time = None

                else:
                    task.status = previous_status
                    task.start_time = None

                task.save(
                    update_fields=[
                        "status",
                        "due_date",
                        "start_time",
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

            if previous_status == "INPROGRESS":
                if task.is_blocked:
                    task.status = "TODO"
                    task.start_time = None
                else:
                    task.status = "INPROGRESS"

                    task.start_time = timezone.now()

            elif previous_status == "REVIEW":
                task.status = "REVIEW"
                task.start_time = None

            else:
                task.status = previous_status
                task.start_time = None

            task.save(
                update_fields=[
                    "status",
                    "start_time",
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

        leave_request.save(
            update_fields=[
                "status",
                "updated_at",
            ]
        )

        return {
            "request_id": leave_request.id,
            "status": leave_request.status,
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
                "new_assignee": (
                    "New assignee is required."
                )
            })

        if (
            leave_action.request.user_id
            == new_assignee.id
        ):
            raise ValidationError({
                "new_assignee": (
                    "The task cannot be transferred "
                    "to the employee who is taking leave."
                )
            })

        if (
            task.assigned_to_id
            == new_assignee.id
        ):
            raise ValidationError({
                "new_assignee": (
                    "The new assignee must be different "
                    "from the current assignee."
                )
            })



        leave_action.previous_assignee = (
            task.assigned_to
        )

        leave_action.previous_task_status = (
            task.status
        )

        leave_action.previous_due_date = (
            task.due_date
        )



        TaskTransferService.assign_task_to_user(
            task=task,
            new_assignee=new_assignee,
            performed_by=manager_user,
            project=task.project,
        )

        leave_action.new_assignee = (
            new_assignee
        )

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

        available_hours = (
            WorkingTimeService.get_working_hours_between(
                workspace=task.project.workspace,
                start_datetime=leave_action.request.leave_end,
                end_datetime=new_due_date,
            )
        )

        if available_hours <= 0:
            raise ValidationError({
                "new_due_date": (
                    "The selected date has no available "
                    "working hours after the leave."
                ),
                "code": "NO_WORKING_TIME_AFTER_LEAVE",
                "available_hours": available_hours,
            })


        expected_duration = (
            task.expected_duration
            or timedelta(0)
        )

        actual_duration = (
            task.actual_duration
            or timedelta(0)
        )

        remaining_duration = max(
            expected_duration - actual_duration,
            timedelta(0),
        )

        remaining_hours = (
            remaining_duration.total_seconds()
            / 3600
        )

        if remaining_hours > available_hours:
            raise ValidationError({
                "new_due_date": (
                    "The selected date does not provide "
                    "enough working hours after the leave."
                ),
                "code": "INSUFFICIENT_WORKING_TIME_AFTER_LEAVE",
                "required_hours": round(
                    remaining_hours,
                    2,
                ),
                "available_hours": round(
                    available_hours,
                    2,
                ),
            })
        leave_action.previous_due_date = task.due_date
        TaskService.validate_dependency_due_date(
            task=task,
            new_due_date=new_due_date,
        )
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
        new_due_date,
    ):
        leave_request = leave_action.request

        if task.status == "PAUSED":
            raise ValidationError({
                "task": (
                    "Task is already paused."
                )
            })

        if not new_due_date:
            raise ValidationError({
                "new_due_date": (
                    "New due date is required."
                )
            })

        if not leave_request.leave_end:
            raise ValidationError({
                "leave_end": (
                    "Leave end date is required."
                )
            })

        now = timezone.now()

        if new_due_date <= now:
            raise ValidationError({
                "new_due_date": (
                    "The new due date must be "
                    "in the future."
                )
            })

        if new_due_date <= leave_request.leave_end:
            raise ValidationError({
                "new_due_date": (
                    "The new due date must be after "
                    "the employee's leave ends."
                )
            })

        if (
            task.due_date
            and new_due_date <= task.due_date
        ):
            raise ValidationError({
                "new_due_date": (
                    "The new due date must be later "
                    "than the current task due date."
                )
            })

        expected_duration = (
            task.expected_duration
            or timedelta(0)
        )

        actual_duration = (
            task.actual_duration
            or timedelta(0)
        )

        current_session = timedelta(0)

        if (
            task.status == "INPROGRESS"
            and task.start_time
        ):
            current_session = (
                now - task.start_time
            )

        worked_duration = (
            actual_duration
            + current_session
        )

        remaining_duration = max(
            expected_duration
            - worked_duration,
            timedelta(0),
        )

        available_after_leave_hours = (
            WorkingTimeService.get_working_hours_between(
                workspace=task.project.workspace,
                start_datetime=leave_request.leave_end,
                end_datetime=new_due_date,
            )
        )

        remaining_hours = (
            remaining_duration.total_seconds()
            / 3600
        )

        if remaining_hours > available_after_leave_hours:
            raise ValidationError({
                "new_due_date": (
                    "The selected date does not provide "
                    "enough working hours after the leave."
                ),
                "code": "INSUFFICIENT_WORKING_TIME_AFTER_LEAVE",
                "required_hours": round(
                    remaining_hours,
                    2,
                ),
                "available_hours": round(
                    available_after_leave_hours,
                    2,
                ),
            })

        leave_action.previous_assignee = (
            task.assigned_to
        )

        leave_action.previous_task_status = (
            task.status
        )

        leave_action.previous_due_date = (
            task.due_date
        )

        leave_action.new_assignee = None
        leave_action.new_due_date = (
            new_due_date
        )

        if (
            task.status == "INPROGRESS"
            and task.start_time
        ):
            task.actual_duration = (
                task.actual_duration
                or timedelta(0)
            ) + (
                now - task.start_time
            )

            task.start_time = None

        TaskService.validate_dependency_due_date(
            task=task,
            new_due_date=new_due_date,
        )

        task.status = "PAUSED"
        task.due_date = new_due_date
        task.end_time = None

        task.save(
            update_fields=[
                "status",
                "due_date",
                "start_time",
                "end_time",
                "actual_duration",
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