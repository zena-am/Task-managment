from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("users", "0005_alter_activitylog_action"),
    ]

    operations = [
        migrations.AlterField(
            model_name="notification",
            name="notification_type",
            field=models.CharField(
                choices=[
                    ("TASK_ASSIGNED", "Task Assigned"),
                    ("TASK_UNASSIGNED", "TASK_UNASSIGNED"),
                    ("SYSTEM_ALERT", "System Alert"),
                    ("COMMENT_ADDED", "New Comment"),
                    ("REPORT_REJECTED", "Report Rejected"),
                    ("REPORT_SUBMITTED", "Report Submitted"),
                    ("INVITATION_RECEIVED", "Invitation Received"),
                    ("INVITATION_ACCEPTED", "Invitation Accepted"),
                    ("INVITATION_REJECTED", "Invitation Rejected"),
                    ("BUG_REPORTED", "Bug Reported"),
                    ("BUG_CLOSED", "Bug Closed"),
                    ("BUG_CONVERTED_TO_TASK", "Bug Converted To Task"),
                ],
                default="SYSTEM_ALERT",
                max_length=30,
            ),
        ),
    ]
