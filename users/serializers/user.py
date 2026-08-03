from rest_framework import serializers
from ..models import Project, ProjectRole
from django.contrib.auth import get_user_model
from users.models import User,Task,WorkSpace,WorkSpaceMember,Project,ProjectRole




class UserSerializer(serializers.ModelSerializer):
    avatar = serializers.SerializerMethodField()
    class Meta:
        model = User
        fields = ['id', 'username', 'email', 'first_name', 'last_name','avatar','phone','is_deleted']


    def to_representation(self, instance):
        if getattr(instance, "is_deleted", False):
            return {
                "id": instance.id,
                "username": "Deleted User",
                "email": None,
                "first_name": "",
                "last_name": "",
                "avatar": None,
                "phone": None,
                "is_deleted": True,
            }
        return super().to_representation(instance)

    def get_avatar(self, obj):
        request = self.context.get('request')
        if obj.avatar:
            avatar_url = obj.avatar.url
            if request:
                return request.build_absolute_uri(avatar_url)
            return avatar_url
        return None

class UpdateProfileSerializer(serializers.ModelSerializer):

    class Meta:
        model = User
        fields = ['first_name', 'last_name', 'avatar', 'phone']

class UserRegisterSerializer(serializers.ModelSerializer):
    password = serializers.CharField(write_only=True)

    class Meta:
        model = User
        fields = ['username', 'email', 'password']

    def create(self, validated_data):
        return User.objects.create_user(**validated_data)






class ProjectMemberDetailSerializer(serializers.ModelSerializer):
    can_delete = serializers.SerializerMethodField()
    role = serializers.SerializerMethodField()
    total_tasks = serializers.SerializerMethodField()
    completed_tasks = serializers.SerializerMethodField()
    user = UserSerializer(read_only=True)
    class Meta:
        model = ProjectRole
        fields = [
            'id',
            'user',
            'role',
            'total_tasks',
            'completed_tasks',
            'can_delete',
            "can_update_role",
        ]
    def get_can_delete(self, obj):
        requester_role = self._get_requester_role(obj)

        can_delete = (
            self._is_workspace_owner(obj)
            or requester_role == "ADMIN"
        )

        if not can_delete:
            return False

        request = self.context.get("request")

        if request and obj.user_id == request.user.id:
            return False

        if obj.role == "ADMIN":
            return False

        return True
    def get_role(self, obj):
        project_id = self.context.get('project_id')
        project_role = ProjectRole.objects.filter(project_id=project_id, user=obj.user).first()
        return obj.role if project_role else 'EMPLOYEE'

    def get_total_tasks(self, obj):
        project_id = self.context.get('project_id')
        return Task.objects.filter(project_id=project_id,assigned_to=obj.user).count()


    def get_completed_tasks(self, obj):
        project_id = self.context.get('project_id')
        return Task.objects.filter(project_id=project_id, assigned_to=obj.user, status='DONE').count()

    def _get_requester_role(self, obj):
        request = self.context.get("request")

        if not request or not request.user.is_authenticated:
            return None

        return ProjectRole.objects.filter(
            project=obj.project,
            user=request.user,
        ).values_list(
            "role",
            flat=True,
        ).first()


    def _is_workspace_owner(self, obj):
        request = self.context.get("request")

        if not request or not request.user.is_authenticated:
            return False


        return (
            obj.project.workspace.creator_id
            == request.user.id
        )
    def get_can_update_role(self, obj):
        requester_role = self._get_requester_role(obj)

        request = self.context.get("request")

        if request and obj.user_id == request.user.id:
            return False

        return (
            self._is_workspace_owner(obj)
            or requester_role in ["ADMIN", "MANAGER"]
        )

###########################################################################################################

User = get_user_model()

class WorkSpaceMemberDetailSerializer(serializers.ModelSerializer):
    role = serializers.SerializerMethodField()
    assigned_projects_count = serializers.SerializerMethodField()
    total_workspace_tasks = serializers.SerializerMethodField()
    completed_workspace_tasks = serializers.SerializerMethodField()
    user = UserSerializer(read_only=True)
    permissions = serializers.SerializerMethodField()


    class Meta:
        model = WorkSpaceMember
        fields = [
            'id',
            'user',
            'role',
            'date_joined',
            'is_pinned',
            'assigned_projects_count',
            'total_workspace_tasks',
            'completed_workspace_tasks',
            'permissions'
        ]

        def get_permissions(self, obj):
            request = self.context.get("request")
            user = request.user if request else None

            if not user or not user.is_authenticated:
                return {
                    "can_view": False,
                    "can_update_role": False,
                    "can_remove": False,
                }

            is_workspace_owner = (
                obj.workspace.creator_id == user.id
            )

            target_is_owner = (
                obj.workspace.creator_id == obj.user_id
            )

            return {
                "can_view": is_workspace_owner,
                "can_update_role": (
                    is_workspace_owner
                    and not target_is_owner
                ),
                "can_remove": (
                    is_workspace_owner
                    and not target_is_owner
                ),
            }
    def get_role(self, obj):
        workspace_id = self.context.get('workspace_id')
        member_role = WorkSpaceMember.objects.filter(workspace_id=workspace_id, user=obj.user).first()
        return obj.role if member_role else 'MEMBER'

    def get_assigned_projects_count(self, obj):
        workspace_id = self.context.get('workspace_id')
        return Project.objects.filter(workspace_id=workspace_id, members=obj.user).count()

    def get_total_workspace_tasks(self, obj):
        workspace_id = self.context.get('workspace_id')
        return Task.objects.filter(project__workspace_id=workspace_id, assigned_to=obj.user).count()

    def get_completed_workspace_tasks(self, obj):
        workspace_id = self.context.get('workspace_id')
        return Task.objects.filter(
            project__workspace_id=workspace_id,
            assigned_to=obj.user,
            status='DONE'
        ).count()
