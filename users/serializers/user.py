from rest_framework import serializers
from ..models import Project, ProjectRole
from ..error_messages import PROJECT_NOT_MEMBER, WORKSPACE_ACCESS_DENIED
from django.contrib.auth import get_user_model
from users.models import User,Task,WorkSpace,WorkSpaceMember,Project,ProjectRole




class UserSerializer(serializers.ModelSerializer):
    avatar = serializers.SerializerMethodField()
    class Meta:
        model = User
        fields = ['id', 'username', 'email', 'first_name', 'last_name','avatar','phone']


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
    phone = serializers.CharField(read_only=True)
    avatar = serializers.SerializerMethodField()
    role = serializers.SerializerMethodField()
    total_tasks = serializers.SerializerMethodField()
    completed_tasks = serializers.SerializerMethodField()

    class Meta:
        model = User
        fields = [
            'id', 'username', 'email', 'first_name', 'last_name',
            'avatar', 'phone', 'role', 'total_tasks', 'completed_tasks'
        ]
    def get_role(self, obj):
        project_id = self.context.get('project_id')
        project_role = ProjectRole.objects.filter(project_id=project_id, user=obj).first()
        return project_role.role if project_role else 'EMPLOYEE'

    def get_total_tasks(self, obj):
        project_id = self.context.get('project_id')
        return Task.objects.filter(project_id=project_id, assigned_to=obj).count()


    def get_completed_tasks(self, obj):
        project_id = self.context.get('project_id')
        return Task.objects.filter(project_id=project_id, assigned_to=obj, status='completed').count()


###########################################################################################################

User = get_user_model()

class WorkSpaceMemberDetailSerializer(serializers.ModelSerializer):
    phone = serializers.CharField(read_only=True)
    avatar = serializers.SerializerMethodField()

    role = serializers.SerializerMethodField()
    assigned_projects_count = serializers.SerializerMethodField()
    total_workspace_tasks = serializers.SerializerMethodField()
    completed_workspace_tasks = serializers.SerializerMethodField()

    class Meta:
        model = User
        fields = [
            'id', 'username', 'email', 'first_name', 'last_name', 'avatar', 'phone',
            'role', 'assigned_projects_count', 'total_workspace_tasks', 'completed_workspace_tasks'
        ]

    def get_avatar(self, obj):
        request = self.context.get('request')
        if hasattr(obj, 'get_avatar_url'):
            return obj.get_avatar_url(request)
        return obj.avatar.url if obj.avatar else None

    def get_role(self, obj):
        workspace_id = self.context.get('workspace_id')
        member_role = WorkSpaceMember.objects.filter(workspace_id=workspace_id, user=obj).first()
        return member_role.role if member_role else 'EMPLOYEE'

    def get_assigned_projects_count(self, obj):
        workspace_id = self.context.get('workspace_id')
        return Project.objects.filter(workspace_id=workspace_id, members=obj).count()

    def get_total_tasks(self, obj):
        workspace_id = self.context.get('workspace_id')
        return Task.objects.filter(project__workspace_id=workspace_id, assigned_to=obj).count()

    def get_completed_tasks(self, obj):
        workspace_id = self.context.get('workspace_id')
        return Task.objects.filter(
            project__workspace_id=workspace_id,
            assigned_to=obj,
            status='DONE'
        ).count()
