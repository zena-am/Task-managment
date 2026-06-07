from users.models import ActivityLog, Notification


def create_activity_log(user, action, action_id, subject_name, target_title, reason=None, is_by_admin=False):
    return ActivityLog.objects.create(
        user=user,
        action=action,
        action_id=action_id,
        changes={
            "subject_name": subject_name,
            "target_title": target_title,
            "reason": reason,
            "is_by_admin": is_by_admin
        }
    )

def create_notification( recipient=None, notification_type=None, title=None, message=None):
    if not all([recipient, notification_type, title, message]):
            return None
    if recipient and notification_type and title and message:
        Notification.objects.create(
            recipient=recipient,
            notification_type=notification_type,
            title=title,
            message=message
        )