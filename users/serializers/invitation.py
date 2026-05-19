from rest_framework import serializers
from ..models import Notification, Invitation


class InvitationSerializer(serializers.ModelSerializer):
    sender_name = serializers.CharField(source='sender.username', read_only=True)
    receiver_name = serializers.CharField(source='receiver.username', read_only=True, default=None)
    project_name = serializers.CharField(source='project.name', read_only=True, default=None)
    workspace_name = serializers.CharField(source='workspace.name', read_only=True)
    class Meta:
        model = Invitation
        fields = [
            'id', 'sender', 'sender_name', 'receiver', 'receiver_name',
            'receiver_email', 'workspace', 'workspace_name',
            'project', 'project_name', 'role', 'status', 'created_at'
        ]
        read_only_fields = ['sender', 'status', 'created_at']

    def create(self, validated_data):

        request = self.context.get('request')
        if request and hasattr(request, 'user'):
            validated_data['sender'] = request.user
        return super().create(validated_data)
