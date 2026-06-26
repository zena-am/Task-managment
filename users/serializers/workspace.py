from rest_framework import serializers
from ..models import WorkSpace, WorkSpaceMember, Task
from users.models import User


class WorkSpaceMemberSerializer(serializers.ModelSerializer):
    id = serializers.IntegerField(source="user.id")
    username = serializers.CharField(source="user.username")
    email = serializers.CharField(source="user.email")

    class Meta:
        model = WorkSpaceMember
        fields = ["id", "username", "email", "role", "date_joined"]






class WorkSpaceSerializer(serializers.ModelSerializer):
        members_details = WorkSpaceMemberSerializer(source="workspacemember_set",many=True,read_only=True)
        # projects = ProjectSerializer(many=True, read_only=True)
        creator = serializers.StringRelatedField(read_only=True)

        user_pinned = serializers.SerializerMethodField()
        user_role = serializers.SerializerMethodField()
        is_owner = serializers.SerializerMethodField()
        stats = serializers.SerializerMethodField()
        permissions = serializers.SerializerMethodField()
        actions = serializers.SerializerMethodField()

        class Meta:
            model = WorkSpace
            fields = [
                'id',
                'name',
            'description',
            'creator',
            'members',
            'members_details',
            'created_at',
            'updated_at',
            'user_pinned',
            'user_role',
            'is_owner',
            'stats',
            'permissions',
            'actions',
        ]

        def _get_request_user(self):
            request = self.context.get('request')
            if request and request.user.is_authenticated:
                return request.user
            return None

        def _get_membership(self, obj):
            user = self._get_request_user()

            if not user:
                return None

            return WorkSpaceMember.objects.filter(
                workspace=obj,
                user=user
            ).first()

        def get_user_pinned(self, obj):
            membership = self._get_membership(obj)
            return membership.is_pinned if membership else False

        def get_user_role(self, obj):
            membership = self._get_membership(obj)
            return membership.role if membership else None

        def get_is_owner(self, obj):
            user = self._get_request_user()
            return bool(user and obj.creator_id == user.id)

        def get_stats(self, obj):
            total_tasks = Task.objects.filter(project__workspace=obj).count()
            done_tasks = Task.objects.filter(
                project__workspace=obj,
                status='DONE'
            ).count()

            progress_rate = round((done_tasks / total_tasks) * 100) if total_tasks > 0 else 0

            return {
                "members_count": obj.members.count(),
                "active_projects_count": obj.projects.filter(status='on_going').count(),
                "progress_timeline": {
                    "percentage": progress_rate,
                    "completed_tasks": done_tasks,
                    "total_tasks": total_tasks
                }
            }

        def get_permissions(self, obj):
            user = self._get_request_user()
            membership = self._get_membership(obj)

            is_member = membership is not None
            is_owner = bool(user and obj.creator_id == user.id)
            is_admin = bool(membership and membership.role == 'ADMIN')

            return {
                "can_open": is_member,
                "can_pin": is_member,
                "can_update": is_owner,
                "can_delete": is_owner,
                "can_transfer_ownership": is_owner,
                "can_leave": is_member and not is_owner,
                "can_invite": is_owner or is_admin,
            }

        def get_actions(self, obj):
            permissions = self.get_permissions(obj)

            actions = []

            if permissions["can_open"]:
                actions.append({
                    "id": "open",
                    "label": "Open Workspace"
                })

            if permissions["can_pin"]:
                actions.append({
                    "id": "toggle_pin",
                    "label": "Pin / Unpin"
                })

            if permissions["can_invite"]:
                actions.append({
                    "id": "invite",
                    "label": "Invite Members"
                })

            if permissions["can_update"]:
                actions.append({
                    "id": "edit",
                    "label": "Edit Workspace"
                })

            if permissions["can_transfer_ownership"]:
                actions.append({
                    "id": "transfer_ownership",
                    "label": "Transfer Ownership"
                })

            if permissions["can_leave"]:
                actions.append({
                    "id": "leave",
                    "label": "Leave Workspace"
                })

            if permissions["can_delete"]:
                actions.append({
                    "id": "delete",
                    "label": "Delete Workspace"
                })

            return actions
###############################################################################

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








class WorkSpaceMemberRoleSerializer(serializers.ModelSerializer):

    user_id = serializers.IntegerField()
    class Meta:
        model = WorkSpaceMember
        fields = ['user_id', 'role']

class WorkSpaceCreateSerializer (serializers.ModelSerializer):
        members_with_roles = WorkSpaceMemberRoleSerializer(many=True, write_only=True, required=False)
        class Meta:
            model =WorkSpace
            fields = ['id', 'name', 'description','members_with_roles']

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
    members_count = serializers.SerializerMethodField()
    user_pinned = serializers.SerializerMethodField()

    class Meta:
        model = WorkSpace
        fields = [
            'id',
            'name',
            'description',
            'members_count',
            'user_pinned',
            'created_at',
        ]

    def get_members_count(self, obj):
        return obj.members.count()

    def get_user_pinned(self, obj):
        request = self.context.get('request')

        if not request or not request.user.is_authenticated:
            return False

        membership = WorkSpaceMember.objects.filter(
            workspace=obj,
            user=request.user
        ).first()

        return membership.is_pinned if membership else False