from rest_framework import viewsets, status
from rest_framework.permissions import IsAuthenticated
from rest_framework.decorators import action
from rest_framework.response import Response
from drf_spectacular.utils import extend_schema, OpenApiExample

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
            value={'status': 'all marked as read'}
        ),
        400: OpenApiExample(
            'Error Response',
            value={"status": "error", "message": "error", "error_details": "string"}
        )
    }
)

@action(detail=True, methods=['post'])
def mark_as_read(self, request, pk=None):
    try:
        notification = self.get_object()
        notification.is_read = True
        notification.save()
        return Response({'status': 'marked as read'}, status=status.HTTP_200_OK)
    except Exception as e:

        return Response({
            "status": "error",
            "message": "error",
            "error_details": str(e)
        }, status=status.HTTP_400_BAD_REQUEST)


@extend_schema(
    summary="تحديث حالة كل الإشعارات إلى مقروء",
    request=None,
    responses={
        200: OpenApiExample(
            'Success Response',
            value={'status': 'all marked as read'}
        ),
        400: OpenApiExample(
            'Error Response',
            value={"status": "error", "message": "error", "error_details": "string"}
        )
    }
)
@action(detail=False, methods=['post'])
def mark_all_as_read(self, request):
    try:
        self.get_queryset().filter(is_read=False).update(is_read=True)
        return Response({'status': 'all marked as read'}, status=status.HTTP_200_OK)
    except Exception as e:

        return Response({
            "status": "error",
            "message": "error",
            "error_details": str(e)
        }, status=status.HTTP_400_BAD_REQUEST)
