from rest_framework import permissions
from .models import ProjectRole, WorkSpaceMember
from rest_framework.permissions import BasePermission

class IsWorkspaceOwnerOrReadOnly(permissions.BasePermission):
    message = "you aren't the creator of this workspace"
    def has_object_permission(self, request, view, obj):
        is_member = WorkSpaceMember.objects.filter(workspace=obj,user=request.user).exists()
        if request.method in permissions.SAFE_METHODS:
            return is_member
        return obj.creator == request.user
class IsWorkspaceOwner(permissions.BasePermission):
    message = "you aren't the creator of this workspace"

    def has_object_permission(self, request, view, obj):

        is_member = WorkSpaceMember.objects.filter(
            workspace=obj.workspace,
            user=request.user
        ).exists()

        if request.method in permissions.SAFE_METHODS:
            return is_member

        return obj.workspace.creator == request.user


class IsProjectManagerOrReadOnly(permissions.BasePermission):
    message = "you aren't the creator of this project"
    def has_object_permission(self, request, view, obj):

        is_member = ProjectRole.objects.filter(project=obj,user=request.user).exists()
        if request.method in permissions.SAFE_METHODS:
            return is_member

        return ProjectRole.objects.filter(project=obj,user=request.user).filter(role__in=['MANAGER', 'ADMIN']).exists()



class TaskPermission(permissions.BasePermission):
    message = "You don't have permission for this task."
    def has_object_permission(self, request, view, obj):
        is_assignee = obj.assigned_to == request.user
        is_project_manager  = ProjectRole.objects.filter(project=obj.project,user=request.user).filter(role__in=['MANAGER', 'ADMIN']).exists()
        if 'assigned_to' in request.data:
            return is_project_manager
        if request.method in permissions.SAFE_METHODS:
            return is_project_manager or is_assignee

        return is_project_manager
    def has_permission(self, request, view):
            if request.method == 'POST':
                project_id = request.data.get('project')
                if not project_id:
                    return False
                return ProjectRole.objects.filter(
                    project_id=project_id,
                    user=request.user,
                    role__in=['MANAGER', 'ADMIN']
                ).exists()
            return True

class CanUpdateTaskStatus(permissions.BasePermission):
    message = "You can update only your assigned task status."

    def has_object_permission(self, request, view, obj):
        is_assignee = obj.assigned_to == request.user
        is_project_manager = ProjectRole.objects.filter(
            project=obj.project,
            user=request.user,
            role__in=["MANAGER", "ADMIN"]
        ).exists()
        return is_assignee or is_project_manager


class IsTeamManagerForProject(permissions.BasePermission):

    message = "You are not a manager."

    def has_permission(self, request, view):

        project_id = (
            view.kwargs.get('project_pk')
            or view.kwargs.get('project_id')
            or view.kwargs.get('pk')
        )

        if not project_id:
            return False
        return ProjectRole.objects.filter(
            project_id=project_id,
            user=request.user,
            role__in=['MANAGER', 'ADMIN']
        ).exists()
    def has_object_permission(self, request, view, obj):
        if not hasattr(obj, 'project'):
            return False
        is_project_manager  = ProjectRole.objects.filter(project=obj.project,user=request.user).filter(role__in=['MANAGER', 'ADMIN']).exists()
        return is_project_manager

class IsTeamManager(permissions.BasePermission):
    message = "You are not a manager of any project."

    def has_permission(self, request, view):

        return ProjectRole.objects.filter(user=request.user,role__in=['MANAGER', 'ADMIN']).exists()



class RequestFormPermission(permissions.BasePermission):
    message = "You do not have permission for this request."

    def has_object_permission(self, request, view, obj):
        is_owner = obj.user == request.user

        is_project_manager = ProjectRole.objects.filter(
            project=obj.project,
            user=request.user,
            role__in=["MANAGER", "ADMIN"]
        ).exists()

        if request.method in permissions.SAFE_METHODS:
            return is_owner or is_project_manager

        if view.action in ["update", "partial_update", "destroy"]:
            return is_owner and obj.status == "PENDING"

        if view.action == "review":
            return is_project_manager and obj.status == "PENDING"

        return False


class TechnicalReportPermission(permissions.BasePermission):
    message = "You do not have permission for this report."

    def has_object_permission(self, request, view, obj):
        is_owner = obj.user == request.user
        is_project_manager = ProjectRole.objects.filter(project=obj.task.project,user=request.user,role__in=["MANAGER", "ADMIN"]).exists()
        if view.action in ["update", "partial_update", "destroy", "submit"]:
            return is_owner and obj.status == "DRAFT"
        if request.method in permissions.SAFE_METHODS:
            return is_owner or is_project_manager
        return False



























class IsProfileComplete(BasePermission):

    message = "complete your profile information"

    def has_permission(self, request, view):
        user = request.user
        if user.is_authenticated:
            return bool(user.avatar and user.phone )
        return False





