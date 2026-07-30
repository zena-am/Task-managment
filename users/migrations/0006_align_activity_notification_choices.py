from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("users", "0005_alter_activitylog_action"),
    ]

    operations = [
        migrations.AlterField(
            model_name="activitylog",
            name="action",
            field=models.CharField(
                choices=[
                    ("ACCOUNT_CREATED", "account created"),
                    ("TASK_ASSIGNED", "Task Assigned"),
                    ("TASK_UNASSIGNED", "Task Unassigned"),
                    ("TASK_DELETED", "Task Deleted"),
                    ("MEMBER_ADDED", "User Added"),
                    ("MEMBER_REMOVED", "User Removed from Workspace"),
                    ("MEMBER_LEFT", "User left from Workspace"),
                    ("ACCOUNT_PURGED", "Account Deleted"),
                    ("GENERAL_UPDATE", "General update"),
                    ("REPORT_REVIEWED", "Report Reviewed"),
                    ("INVITATION_SENT", "Invitation Sent"),
                    ("INVITATION_ACCEPTED", "Invitation Accepted"),
                    ("INVITATION_REJECTED", "Invitation Rejected"),
                    ("REQUEST_CREATED", "Request Created"),
                    ("REQUEST_UPDATED", "Request Updated"),
                    ("REQUEST_DELETED", "Request Deleted"),
                    ("REQUEST_REVIEWED", "Request Reviewed"),
                    ("REPORT_DRAFT_CREATED", "Report Draft Created"),
                    ("REPORT_DRAFT_UPDATED", "Report Draft Updated"),
                    ("REPORT_DELETED", "Report Deleted"),
                    ("REPORT_SUBMITTED", "Report Submitted"),
                    ("BUG_REPORTED", "Bug Reported"),
                    ("BUG_UPDATED", "Bug Updated"),
                    ("BUG_DELETED", "Bug Deleted"),
                    ("BUG_CONVERTED_TO_TASK", "Bug Converted To Task"),
                    ("ROLE_UPDATED", "Role Updated"),
                    ("BULK_TASK_UPDATED", "Bulk Task Updated"),
                    ("WORKSPACE_ARCHIVED", "Workspace Archived"),
                    ("WORKSPACE_RESTORED", "Workspace Restored"),
                    ("PROJECT_ARCHIVED", "Project Archived"),
                    ("PROJECT_RESTORED", "Project Restored"),
                    ("TASK_ARCHIVED", "Task Archived"),
                    ("TASK_RESTORED", "Task Restored"),
                ],
                default="GENERAL_UPDATE",
                max_length=100,
            ),
        ),
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
                max_length=20,
            ),
        ),
    ]
