from users.models import ActivityLog, Notification


def create_activity_log(user, action, action_id, changes=None, **extra_changes):
    """Create an activity log entry using one normalized changes payload.

    Older services in this app used to pass fields like subject_name,
    target_title, reason, and is_by_admin as separate keyword arguments.
    Keeping **extra_changes here prevents runtime TypeError and stores those
    values inside the JSON changes field used by ActivityLogSerializer.
    """
    payload = {}
    if changes:
        payload.update(changes)
    payload.update({key: value for key, value in extra_changes.items() if value is not None})

    return ActivityLog.objects.create(
        user=user,
        action=action,
        action_id=action_id,
        changes=payload,
    )


def create_notification(recipient=None, notification_type=None, title=None, message=None, navigation_target=None):
    if not all([recipient, notification_type, title, message]):
        return None

    return Notification.objects.create(
        recipient=recipient,
        notification_type=notification_type,
        title=title,
        message=message,
        navigation_target=navigation_target,
    )
