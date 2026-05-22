from users.models import Notification
from rest_framework import serializers

class NotificationSerializer(serializers.ModelSerializer):
        class Meta:
                model=Notification
                fields = ['id', 'notification_type', 'title','message', 'is_read', 'created_at', 'navigation_target']
                read_only_fields = ['id', 'notification_type', 'created_at']

