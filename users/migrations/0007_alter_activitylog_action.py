from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [("users", "0006_alter_notification_notification_type")]

    operations = [
        migrations.AlterField(
            model_name="activitylog",
            name="action",
            field=models.CharField(
                choices=[
                    ("ACCOUNT_CREATED", "account created"),
                    ("WORKSPACE_CREATED", "Workspace Created"),
                    ("WORKSPACE_UPDATED", "Workspace Updated"),
                    ("WORKSPACE_DELETED", "Workspace Deleted"),
                    ("WORKSPACE_LEFT", "Workspace Left"),
                    ("WORKSPACE_OWNERSHIP_TRANSFERRED", "Workspace Ownership Transferred"),
                    ("PROJECT_CREATED", "Project Created"),
                    ("PROJECT_UPDATED", "Project Updated"),
                    ("PROJECT_DELETED", "Project Deleted"),
                    ("PROJECT_LEFT", "Project Left"),
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
    ]
