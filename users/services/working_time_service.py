from datetime import datetime, timedelta
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from django.utils import timezone


class WorkingTimeService:
    DAYS = [
        "MON",
        "TUE",
        "WED",
        "THU",
        "FRI",
        "SAT",
        "SUN",
    ]

    @staticmethod
    def _workspace_timezone(workspace):
        schedule = workspace.working_schedule
        try:
            return ZoneInfo(schedule.timezone or "UTC")
        except ZoneInfoNotFoundError:
            return timezone.get_current_timezone()

    @staticmethod
    def _as_workspace_datetime(*, workspace, value):
        workspace_tz = WorkingTimeService._workspace_timezone(workspace)

        if timezone.is_naive(value):
            value = timezone.make_aware(value, workspace_tz)

        return value.astimezone(workspace_tz)

    @staticmethod
    def get_working_intervals(
        *,
        workspace,
        start_datetime,
        end_datetime,
    ):
        """Return real working intervals in the workspace timezone.

        The result respects each day's enabled/start/end values from
        weekly_schedule. 24-hour workspaces return one continuous interval.
        """
        if start_datetime is None or end_datetime is None:
            return []

        start_local = WorkingTimeService._as_workspace_datetime(
            workspace=workspace,
            value=start_datetime,
        )
        end_local = WorkingTimeService._as_workspace_datetime(
            workspace=workspace,
            value=end_datetime,
        )

        if start_local >= end_local:
            return []

        schedule = workspace.working_schedule

        if schedule.is_24_hours:
            return [(start_local, end_local)]

        weekly_schedule = schedule.weekly_schedule or {}
        intervals = []
        current_date = start_local.date()

        while current_date <= end_local.date():
            day_name = WorkingTimeService.DAYS[current_date.weekday()]
            day_schedule = weekly_schedule.get(day_name)

            if day_schedule and day_schedule.get("enabled"):
                start_text = day_schedule.get("start")
                end_text = day_schedule.get("end")

                if start_text and end_text:
                    start_time = datetime.strptime(
                        start_text,
                        "%H:%M",
                    ).time()
                    end_time = datetime.strptime(
                        end_text,
                        "%H:%M",
                    ).time()

                    day_start = datetime.combine(
                        current_date,
                        start_time,
                        tzinfo=start_local.tzinfo,
                    )
                    day_end = datetime.combine(
                        current_date,
                        end_time,
                        tzinfo=start_local.tzinfo,
                    )

                    interval_start = max(start_local, day_start)
                    interval_end = min(end_local, day_end)

                    if interval_end > interval_start:
                        intervals.append(
                            (interval_start, interval_end)
                        )

            current_date += timedelta(days=1)

        return intervals

    @staticmethod
    def get_deadline_schedule_status(*, workspace, value):
        """Return whether a deadline falls inside the workspace schedule.

        This is intentionally independent from employee availability. It is
        used for both assigned and unassigned tasks so an unassigned task
        cannot bypass the weekly schedule rules.
        """
        if value is None:
            return {
                "valid": False,
                "reason": "DUE_DATE_REQUIRED",
                "day": None,
                "start": None,
                "end": None,
            }

        local_value = WorkingTimeService._as_workspace_datetime(
            workspace=workspace,
            value=value,
        )
        schedule = workspace.working_schedule

        if schedule.is_24_hours:
            return {
                "valid": True,
                "reason": None,
                "day": WorkingTimeService.DAYS[local_value.weekday()],
                "start": "00:00",
                "end": "23:59",
            }

        day_name = WorkingTimeService.DAYS[local_value.weekday()]
        day_schedule = (schedule.weekly_schedule or {}).get(day_name) or {}

        if not day_schedule.get("enabled"):
            return {
                "valid": False,
                "reason": "DUE_DATE_ON_NON_WORKING_DAY",
                "day": day_name,
                "start": day_schedule.get("start"),
                "end": day_schedule.get("end"),
            }

        start_text = day_schedule.get("start")
        end_text = day_schedule.get("end")
        if not start_text or not end_text:
            return {
                "valid": False,
                "reason": "WORKING_SCHEDULE_INCOMPLETE",
                "day": day_name,
                "start": start_text,
                "end": end_text,
            }

        start_time = datetime.strptime(start_text, "%H:%M").time()
        end_time = datetime.strptime(end_text, "%H:%M").time()
        local_time = local_value.time().replace(tzinfo=None)

        valid = start_time <= local_time <= end_time
        return {
            "valid": valid,
            "reason": None if valid else "DUE_DATE_OUTSIDE_WORKING_HOURS",
            "day": day_name,
            "start": start_text,
            "end": end_text,
        }

    @staticmethod
    def get_working_hours_between(
        *,
        workspace,
        start_datetime,
        end_datetime,
    ):
        intervals = WorkingTimeService.get_working_intervals(
            workspace=workspace,
            start_datetime=start_datetime,
            end_datetime=end_datetime,
        )

        total_seconds = sum(
            (interval_end - interval_start).total_seconds()
            for interval_start, interval_end in intervals
        )

        return round(total_seconds / 3600, 2)

    @staticmethod
    def add_working_hours(
        *,
        workspace,
        start_datetime,
        hours,
    ):
        if hours <= 0:
            return start_datetime

        original_tz = start_datetime.tzinfo
        current = WorkingTimeService._as_workspace_datetime(
            workspace=workspace,
            value=start_datetime,
        )
        remaining = float(hours)

        # Search in bounded chunks so disabled days and irregular schedules
        # are handled without assuming a fixed number of hours per day.
        for _ in range(24):  # up to roughly two years of schedule search
            window_end = current + timedelta(days=31)
            intervals = WorkingTimeService.get_working_intervals(
                workspace=workspace,
                start_datetime=current,
                end_datetime=window_end,
            )

            for interval_start, interval_end in intervals:
                available = (
                    interval_end - interval_start
                ).total_seconds() / 3600

                if remaining <= available:
                    result = interval_start + timedelta(hours=remaining)
                    if original_tz is not None:
                        return result.astimezone(original_tz)
                    return result

                remaining -= available

            current = window_end

        raise ValueError(
            "Unable to calculate a due date from the workspace schedule."
        )
