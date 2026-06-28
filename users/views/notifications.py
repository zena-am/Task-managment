from rest_framework import viewsets, status
from rest_framework.permissions import IsAuthenticated
from rest_framework.decorators import action
from rest_framework.response import Response
from drf_spectacular.utils import extend_schema, OpenApiExample

from users.errors.messages.success import success_response
from ..models import Notification
from ..serializers import NotificationSerializer


class NotificationViewSet(viewsets.ModelViewSet):
    permission_classes = [IsAuthenticated]
    serializer_class = NotificationSerializer

    def get_queryset(self):
        return Notification.objects.filter(recipient=self.request.user)

    @extend_schema(
        summary="تحديث حالة الإشعار إلى مقروء",
        request=None,
        responses={
            200: OpenApiExample(
                'Success Response',
                value={'status': 'marked as read'}
            )
        }
    )
    @action(detail=True, methods=['post'])
    def mark_as_read(self, request, pk=None):
        notification = self.get_object()
        notification.is_read = True
        notification.save(update_fields=['is_read', 'updated_at'])

        return Response(success_response(
            message="Notification marked as read successfully",
            code="NOTIFICATION_MARKED_AS_READ",
            data={"notification_id": notification.id, "is_read": True}
        ), status=status.HTTP_200_OK)

    @extend_schema(
        summary="تحديث حالة كل الإشعارات إلى مقروء",
        request=None,
        responses={
            200: OpenApiExample(
                'Success Response',
                value={'status': 'all marked as read'}
            )
        }
    )
    @action(detail=False, methods=['post'])
    def mark_all_as_read(self, request):
        updated_count = self.get_queryset().filter(is_read=False).update(is_read=True)

        return Response(success_response(
            message="All notifications marked as read successfully",
            code="ALL_NOTIFICATIONS_MARKED_AS_READ",
            data={"updated_count": updated_count}
        ), status=status.HTTP_200_OK)
