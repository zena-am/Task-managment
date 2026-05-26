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
####
from users.models import Project, ProjectMember
from users.services.invitationsService import InvitationService


class ProjectService:
    @staticmethod
    def get_user_projects(user):
        return Project.objects.filter(workspace__members=user).distinct()

    @staticmethod
    def create_project(serializer, user, data):
        project = serializer.save()

        ProjectMember.objects.get_or_create(
            project=project,
            user=user,
            defaults={"role": "ADMIN"}
        )

        invitation_result = None

        if ProjectService._has_project_members_data(data):
            invitation_data = ProjectService._build_project_invitation_data(project, data)
            invitation_result = InvitationService.send_project_invitation(user, invitation_data)

        return {
            "project": project,
            "invitation_result": invitation_result
        }

    @staticmethod
    def _has_project_members_data(data):
        member_emails = ProjectService._get_value(data, "member_emails")
        members_ids = ProjectService._get_value(data, "members_ids")

        return bool(member_emails or members_ids)

    @staticmethod
    def _build_project_invitation_data(project, data):
        return {
            "project_id": project.id,
            "workspace_id": project.workspace.id,
            "role": ProjectService._get_value(data, "role") or "DEV",
            "member_emails": ProjectService._get_list_value(data, "member_emails"),
            "members_ids": ProjectService._get_list_value(data, "members_ids"),
        }

    @staticmethod
    def _get_value(data, key):
        if hasattr(data, "get"):
            return data.get(key)
        return None

    @staticmethod
    def _get_list_value(data, key):
        if hasattr(data, "getlist"):
            return data.getlist(key)

        value = data.get(key) if hasattr(data, "get") else None

        if not value:
            return []

        if isinstance(value, list):
            return value

        return [value]