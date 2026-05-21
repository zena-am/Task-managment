from django.utils import timezone
from users.models import ProjectRole
from users.errors.exceptions import (
    TaskAlreadyAssigned, InvalidStatusError, PermissionDeniedError
)


class TaskService:

    @staticmethod
    def claim_task(task, user):
        if task.assigned_to is not None:
            raise TaskAlreadyAssigned()

        task.assigned_to = user
        task.status = "TODO"
        task.save()

        return task

    @staticmethod
    def update_status(task, user, status_value):

        allowed_choices = ["TODO", "INPROGRESS", "DONE"]

        if status_value not in allowed_choices:
            raise InvalidStatusError()

        if task.status == "DONE" and status_value in ["TODO", "INPROGRESS"]:
            raise InvalidStatusError()

        is_project_admin = ProjectRole.objects.filter(
            project=task.project,
            user=user,
            role='ADMIN'
        ).exists()

        if user != task.assigned_to and user != task.supervisor and not is_project_admin:
            raise PermissionDeniedError()

        if status_value == "INPROGRESS" and not task.start_time:
            task.start_time = timezone.now()

        if status_value == "DONE":
            if not task.start_time:
                task.start_time = timezone.now()

            task.end_time = timezone.now()
            task.actual_duration = task.end_time - task.start_time

        task.status = status_value
        task.save()

        return task


    

    def perform_create(self, serializer):
        assigned_to_user = serializer.validated_data.get('assigned_to')

        if assigned_to_user is not None:
            initial_status = 'TODO'
        else:
            initial_status = 'UNASSIGNED'

        serializer.save(
            supervisor=self.request.user,
            user=self.request.user,
            status=initial_status
        )



    def perform_update(self, serializer):
        status = self.request.data.get('status')
        instance = self.get_object()
        if status == 'INPROGRESS' and not instance.start_time:
            serializer.save(start_time=timezone.now())
        elif status == 'DONE':
            now = timezone.now()
            actual_dur = now - instance.start_time if instance.start_time else None
            serializer.save(end_time=now, actual_duration=actual_dur)
        else:
            serializer.save()
