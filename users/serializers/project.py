from rest_framework import serializers

from users.errors.exceptions import ProjectNotMember, WorkspaceAccessDenied
from ..models import Project, ProjectRole
from drf_spectacular.utils import extend_schema_field
from users.models import User




class ProjectSerializer(serializers.ModelSerializer):

    workspace_name = serializers.ReadOnlyField(source='workspace.name')
    status_display = serializers.CharField(source='get_status_display', read_only=True)
    members = serializers.SerializerMethodField()
    class Meta:
        model = Project
        fields = [
            'id', 'workspace', 'workspace_name', 'name', 'description',
            'status', 'status_display', 'deadline', 'created_at', 'updated_at', 'members'
        ]
        read_only_fields = ['created_at']


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
        fields = ['id', 'workspace', 'name', 'description', 'deadline', 'status', 'members_with_roles']

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