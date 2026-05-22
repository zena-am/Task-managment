from users.models import Task, User
from django.shortcuts import get_object_or_404


class TaskTransferService:

    @staticmethod
    def get_orphaned_tasks(project):
        try:
            system_bot = User.objects.get(username='system_bot')
        except User.DoesNotExist:
            return []

        return Task.objects.filter(
            project=project,
            supervisor=system_bot
        )

    @staticmethod
    def transfer_tasks(project, new_supervisor):
        try:
            system_bot = User.objects.get(username='system_bot')
        except User.DoesNotExist:
            return 0

        tasks = Task.objects.filter(
            project=project,
            supervisor=system_bot
        )

        count = tasks.count()

        if count == 0:
            return 0

        tasks.update(supervisor=new_supervisor)

        return count
