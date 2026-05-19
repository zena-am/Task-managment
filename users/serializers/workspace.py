from rest_framework import serializers
from ..models import WorkSpace, WorkSpaceMember, Task
from ..error_messages import PROJECT_NOT_MEMBER, WORKSPACE_ACCESS_DENIED
from users.models import User





class WorkSpaceSerializer(serializers.ModelSerializer):
        members_details = serializers.SerializerMethodField()
        # projects = ProjectSerializer(many=True, read_only=True)
        creator = serializers.StringRelatedField(read_only=True)
        actions = serializers.SerializerMethodField()
        stats = serializers.SerializerMethodField()
        is_owner= serializers.SerializerMethodField()
        class Meta:
            model = WorkSpace
            fields = [
            'id', 'name', 'description',
            'creator',
            'members', 'members_details',
            'created_at', 'updated_at','stats','actions','is_owner']

        def get_is_owner(self, obj):
            request = self.context.get('request')
            if request and request.user.is_authenticated:

                return obj.creator == request.user
            return False
        def get_members_details(self, obj):
            workspace_members = WorkSpaceMember.objects.filter(workspace=obj).select_related('user')
            return [
            {
                "username": member.user.username,
                "email": member.user.email,
                "position": member.role,
                "date_joined": member.date_joined
            }
            for member in workspace_members
        ]

        def get_actions(self, obj):
            request = self.context.get('request')
            if request and request.user.is_authenticated:
                if obj.creator == request.user:
                    return [
                    {"id": "edit", "label": "Edit Workspace",},
                    {"id": "delete", "label": "Delete Workspace",}
                ]
            else:
                return [
                    {"id": "toggle_pin", "label": "Pin / Unpin"},
                    {"id": "leave", "label": "Leave Workspace", }
                ]
            return []
        def get_stats(self, obj):
            total_tasks = Task.objects.filter(project__workspace=obj).count()
            done_tasks = Task.objects.filter(project__workspace=obj, status='DONE').count()

            if total_tasks > 0:
                progress_rate = round((done_tasks / total_tasks) * 100)
            else:
                progress_rate = 0

            return {
                "members_count": obj.members.count(),
                "active_projects_count": obj.projects.filter(status='on_going').count(),
                "progress_timeline": {
                    "percentage": progress_rate,
                    "completed_tasks": done_tasks,
                    "total_tasks": total_tasks
                }
            }

class WorkSpaceMemberRoleSerializer(serializers.ModelSerializer):

    user_id = serializers.IntegerField()
    class Meta:
        model = WorkSpaceMember
        fields = ['user_id', 'role']

class WorkSpaceCreateSerializer (serializers.ModelSerializer):
        members_with_roles = WorkSpaceMemberRoleSerializer(many=True, write_only=True, required=False)
        class Meta:
            model =WorkSpace
            fields = ['id', 'name', 'description','is_pinned','members_with_roles']

        def create(self, validated_data):
            members_data = validated_data.pop('members_with_roles', [])

            workspace = WorkSpace.objects.create(**validated_data)

            for member_item in members_data:
                user_id = member_item['user_id']
                role = member_item['role']

                WorkSpaceMember.objects.create(
                    workspace=workspace,
                    user_id=user_id,
                    role=role
                )

            return workspace


class WorkSpaceListSerializer(serializers.ModelSerializer):
        class Meta:
            model=WorkSpace
            fields=['name','members_details','created_at']



