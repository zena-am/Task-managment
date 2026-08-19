from datetime import datetime, timedelta


class WorkingTimeService:
    @staticmethod
    def get_working_hours_between(
        *,
        workspace,
        start_datetime,
        end_datetime,
    ):

        if start_datetime >= end_datetime:
            return 0

        schedule = workspace.working_schedule

        if schedule.is_24_hours:
            seconds = (
                end_datetime - start_datetime
            ).total_seconds()

            return round(seconds / 3600, 2)

        total_hours = 0

        current = start_datetime

        weekly_schedule = (
            schedule.weekly_schedule
            or {}
        )

        days = [
            "MON",
            "TUE",
            "WED",
            "THU",
            "FRI",
            "SAT",
            "SUN",
        ]

        while current.date() <= end_datetime.date():

            day_name = days[current.weekday()]

            day_schedule = weekly_schedule.get(day_name)

            if (
                not day_schedule
                or not day_schedule.get("enabled")
            ):
                current = datetime.combine(
                    current.date() + timedelta(days=1),
                    datetime.min.time(),
                    tzinfo=current.tzinfo,
                )
                continue

            start_time = datetime.strptime(
                day_schedule["start"],
                "%H:%M",
            ).time()

            end_time = datetime.strptime(
                day_schedule["end"],
                "%H:%M",
            ).time()

            day_start = datetime.combine(
                current.date(),
                start_time,
                tzinfo=current.tzinfo,
            )

            day_end = datetime.combine(
                current.date(),
                end_time,
                tzinfo=current.tzinfo,
            )

            period_start = max(
                current,
                day_start,
            )

            period_end = min(
                end_datetime,
                day_end,
            )

            if period_end > period_start:

                seconds = (
                    period_end - period_start
                ).total_seconds()

                total_hours += (
                    seconds / 3600
                )

            current = datetime.combine(
                current.date() + timedelta(days=1),
                datetime.min.time(),
                tzinfo=current.tzinfo,
            )

        return round(
            total_hours,
            2,
        )














    @staticmethod
    def add_working_hours(
        *,
        workspace,
        start_datetime,
        hours,
    ):

        schedule = workspace.working_schedule

        if schedule.is_24_hours:

            return (
                start_datetime
                + timedelta(hours=hours)
            )


        current = start_datetime

        remaining = hours

        weekly_schedule = (
            schedule.weekly_schedule
            or {}
        )


        while remaining > 0:


            days = [
                "MON",
                "TUE",
                "WED",
                "THU",
                "FRI",
                "SAT",
                "SUN",
            ]

            day_name = days[current.weekday()]


            day_schedule = (
                weekly_schedule.get(day_name)
            )


            if (
                day_schedule
                and day_schedule.get("enabled")
            ):

                start_time = datetime.strptime(
                    day_schedule["start"],
                    "%H:%M",
                ).time()


                end_time = datetime.strptime(
                    day_schedule["end"],
                    "%H:%M",
                ).time()


                day_start = datetime.combine(
                    current.date(),
                    start_time,
                    tzinfo=current.tzinfo,
                )


                day_end = datetime.combine(
                    current.date(),
                    end_time,
                    tzinfo=current.tzinfo,
                )


                if current < day_start:
                    current = day_start


                if current < day_end:

                    available_hours = (
                        day_end - current
                    ).total_seconds() / 3600


                    if remaining <= available_hours:

                        return (
                            current
                            + timedelta(
                                hours=remaining
                            )
                        )


                    remaining -= available_hours


            current = datetime.combine(
                current.date() + timedelta(days=1),
                datetime.min.time(),
                tzinfo=current.tzinfo,
            )


        return current