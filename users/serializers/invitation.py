from rest_framework import serializers
from ..models import Invitation


class InvitationSerializer(serializers.ModelSerializer):
    sender_name = serializers.CharField(source='sender.username', read_only=True)
    receiver_name = serializers.CharField(source='receiver.username', read_only=True, default=None)
    project_name = serializers.CharField(source='project.name', read_only=True, default=None)
    workspace_name = serializers.CharField(source='workspace.name', read_only=True)
    receiver_email = serializers.EmailField(required=False)
    receiver_emails = serializers.ListField(child=serializers.JSONField(), required=False, write_only=True)
    members_ids = serializers.ListField(child=serializers.JSONField(), required=False, write_only=True)
    permissions = serializers.SerializerMethodField()

    class Meta:
        model = Invitation
        fields = [
            'id', 'sender', 'sender_name', 'receiver', 'receiver_name',
            'receiver_email', 'receiver_emails', 'members_ids',
            'workspace', 'workspace_name', 'project', 'project_name',
            'role', 'status', 'permissions', 'created_at',
        ]
        read_only_fields = ['sender', 'status', 'created_at']

    def get_permissions(self, obj):
        request = self.context.get("request")
        user = request.user if request else None

        is_receiver = obj.receiver_email == (user.email if user else None)
        is_sender = obj.sender_id == (user.id if user else None)

        return {
            "can_accept": is_receiver and obj.status == "PENDING",
            "can_reject": is_receiver and obj.status == "PENDING",
            "can_revoke": is_sender and obj.status == "PENDING",
            "can_view": is_receiver or is_sender,
        }
