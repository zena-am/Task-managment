from users.models import ProjectRole
from users.services import WorkspaceService


class ProjectService:

    @staticmethod
    def create_project(serializer, user, data):
        project = serializer.save()

        ProjectRole.objects.get_or_create(
            project=project,
            user=user,
            defaults={'role': 'ADMIN'}
        )

        members_ids = data.get('members_ids', [])
        member_emails = data.get('member_emails', [])

        if members_ids:
            ProjectService.handle_members_ids(project, members_ids)

        if member_emails:
            ProjectService.handle_project_invitations(project, member_emails, user, data)

        return project
