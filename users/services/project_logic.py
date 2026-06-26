from users.errors.exceptions import PermissionDeniedError, ProjectAlreadyExists
from users.models import Project, ProjectRole
from users.models import  ProjectRole
from users.services.invitationsService import InvitationService


class ProjectServiceLogic:
    @staticmethod
    def create(serializer, request):
            workspace = serializer.validated_data["workspace"]
            name = serializer.validated_data["name"]

            if Project.objects.filter(
                workspace=workspace,
                name=name
            ).exists():
                raise ProjectAlreadyExists()

            project = serializer.save()
            ProjectRole.objects.get_or_create(
                    project=project,
                    user=request.user,
                    defaults={'role': 'ADMIN'}
                )

            print(request.data)
            invitation_data = {
                "project_id": project.id,
                "role": request.data.get("role", "EMPLOYEE"),
                "receiver_emails": request.data.get("receiver_emails", []),
                "members_ids": request.data.get("members_ids", [])
            }
            print(invitation_data)

            invitation_results = None
            if invitation_data["receiver_emails"] or invitation_data["members_ids"]:

                    invitation_results = InvitationService.send_project_invitation(
                    sender=request.user,
                    data=invitation_data
                )
            print(invitation_results)
            return {
                "project": project,
                "invitation_results": invitation_results
            }




@staticmethod
def update_user_role(project, target_user, new_role, request_user):
    if not ProjectRole.objects.filter(project=project, user=request_user, role='ADMIN').exists():
        raise PermissionDeniedError()

    role_obj, created = ProjectRole.objects.update_or_create(
        project=project,
        user=target_user,
        defaults={'role': new_role}
    )
    return role_obj