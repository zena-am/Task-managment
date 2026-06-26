from rest_framework import serializers
from users.errors.exceptions import ProjectNotMember, WorkspaceAccessDenied
from ..models import Project, ProjectRole, Task
from drf_spectacular.utils import extend_schema_field
from users.models import User


class ProjectSerializer(serializers.ModelSerializer):


    workspace_name = serializers.ReadOnlyField(source='workspace.name')
    status_display = serializers.CharField(source='get_status_display', read_only=True)
    members = serializers.SerializerMethodField()
    actions = serializers.SerializerMethodField()
    is_owner= serializers.SerializerMethodField()
    stats = serializers.SerializerMethodField()
    permissions = serializers.SerializerMethodField()

    class Meta:
        model = Project
        fields = [
            'id', 'workspace', 'workspace_name', 'name', 'description','actions','stats',
            'status', 'status_display', 'deadline', 'created_at', 'updated_at', 'members','is_owner','permissions',
        ]
        read_only_fields = ['created_at']

    def get_permissions(self, obj):
        request = self.context.get('request')
        user = request.user if request else None

        if not user or not user.is_authenticated:
            return {
                "can_view": False,
                "can_edit": False,
                "can_delete": False,
                "can_leave": False,
                "can_invite": False,
            }

        is_owner = obj.workspace.creator_id == user.id

        is_member = ProjectRole.objects.filter(
            project=obj,
            user=user
        ).exists()

        is_admin = ProjectRole.objects.filter(
            project=obj,
            user=user,
            role__in=["ADMIN", "MANAGER"]
        ).exists()

        return {
            "can_view": is_member,
            "can_edit": is_owner or is_admin,
            "can_delete": is_owner,
            "can_leave": is_member and not is_owner,
            "can_invite": is_owner or is_admin,
        }
    def get_stats(self, obj):
        total_tasks = Task.objects.filter(project=obj).count()
        done_tasks = Task.objects.filter(project=obj, status='DONE').count()

        if total_tasks > 0:
            progress_rate = round((done_tasks / total_tasks) * 100)
        else:
            progress_rate = 0

        return {
            "members_count": obj.members.count(),
            "progress_timeline": {
                "percentage": progress_rate,
                "completed_tasks": done_tasks,
                "total_tasks": total_tasks
            }
        }
    def get_actions(self, obj):
        request = self.context.get('request')
        if request and request.user.is_authenticated:
            if obj.workspace.creator == request.user:
                return [
                {"id": "edit", "label": "Edit Project",},
                {"id": "delete", "label": "Delete Project",}
            ]
        else:
            return [
                {"id": "leave", "label": "Leave project", }
            ]
        return []

    def get_is_owner(self, obj):
        request = self.context.get('request')
        if request and request.user.is_authenticated:

            return obj.workspace.creator == request.user
        return False



    def validate_workspace(self, value):
        user = self.context['request'].user
        if not value.members.filter(id=user.id).exists():
            raise WorkspaceAccessDenied
        return value


    @extend_schema_field(serializers.ListSerializer(child=serializers.DictField(child=serializers.CharField())))
    def get_members(self, obj):
        project_roles = ProjectRole.objects.filter(project=obj).select_related('user')
        request = self.context.get('request')
        members_list = []


        for pr in project_roles:
            user = pr.user
            avatar_url = None
            if user.avatar:
                avatar_url = user.avatar.url
                if request:
                    avatar_url = request.build_absolute_uri(avatar_url)


            members_list.append({
                'id': user.id,
                'username': user.username,
                'first_name': user.first_name,
                'last_name': user.last_name,
                'role': pr.role,
                'avatar': avatar_url,
                'date_joined': pr.date_joined
            })
        return members_list


class ProjectMemberRoleSerializer(serializers.ModelSerializer):

    is_owner = serializers.SerializerMethodField()
    user_id = serializers.IntegerField(source='user.id')

    class Meta:
        model = ProjectRole
        fields = ['user_id', 'is_owner']
    def get_is_owner(self, obj):
            return obj.role == 'OWNER'


class ProjectCreateSerializer(serializers.ModelSerializer):
    members_with_roles = ProjectMemberRoleSerializer(many=True, write_only=True, required=False)

    class Meta:
        model = Project
        fields = ['id', 'workspace', 'name', 'description', 'deadline',  'members_with_roles']

    def validate_workspace(self, value):
        user = self.context['request'].user
        if not value.members.filter(id=user.id).exists():
            raise ProjectNotMember
        return value



    def create(self, validated_data):
        members_data = validated_data.pop('members_with_roles', [])
        project = Project.objects.create(**validated_data)


        for member_item in members_data:
            user_id = member_item['user_id']
            role = member_item['role']

            ProjectRole.objects.create(
                project=project,
                user_id=user_id,
                role=role
            )

        return project


