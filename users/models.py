from datetime import timedelta

from django.db import models
from django.shortcuts import render
from django.contrib.auth.models import AbstractUser, UserManager
from config import settings
from users.managers import ActiveUserManager
from django.db import models
from django.utils.text import slugify
from django.utils import timezone
from django.contrib.auth.hashers import make_password
from django.core.validators import RegexValidator
from users.errors.exceptions import PhoneValidationError
import uuid
from users.errors.messages.ErrorCode import ErrorMessages


class User(AbstractUser):
        email=models.EmailField(unique=True)
        avatar = models.ImageField(upload_to="profiles/", null=True, blank=True)
        phone_regex = RegexValidator(regex=r"^\+?1?\d{9,15}$",message=ErrorMessages.PHONE_VALIDATION_ERROR)
        phone = models.CharField(max_length=20,blank=True, validators=[phone_regex])
        is_deleted = models.BooleanField(default=False, db_index=True)
        deleted_at = models.DateTimeField(null=True, blank=True)
        is_available_for_tasks = models.BooleanField(default=True)
        objects = ActiveUserManager()
        all_objects = UserManager()

        class Meta:
                base_manager_name = "all_objects"
                default_manager_name = "objects"

        @property
        def profile_data(self):
                return {
                "full_name": f"{self.first_name} {self.last_name}".strip() or self.username,
                "image": self.avatar.url if self.avatar else None,
                "phone": self.phone}

        def soft_delete(self):
                if self.is_deleted:
                        return False
                self.is_deleted = True
                self.deleted_at = timezone.now()
                self.is_active = False
                self.save(update_fields=["is_deleted", "deleted_at", "is_active"])
                return True

        def restore(self):
                if not self.is_deleted:
                        return False
                self.is_deleted = False
                self.deleted_at = None
                self.is_active = True
                self.save(update_fields=["is_deleted", "deleted_at", "is_active"])
                return True

def get_default_user():
        user, created = User.all_objects.get_or_create(
        username='system_bot',
        defaults={
                'email': 'system_bot@yourdomain.local',
                'is_active': False,
                'password': make_password(str(uuid.uuid4())),
                'first_name': 'System',
                'last_name': 'Automated Bot'
                }
        )
        return user



def ProfileImage(instance,filename):
        return "avatar_{0}/{1}".format(instance.user.id,filename)

###للtask
def TaskFilePath(instance, filename):
        return "tasksFile/user_{0}/{1}".format(instance.user.id, filename)
def TaskPhotoPath(instance, filename):
        return "tasksPhoto/user_{0}/{1}".format(instance.user.id, filename)
##
def CommentAttachmentPath(instance, filename):
        return "comment/user_{0}/{1}".format(instance.user.id,filename)
###reports
def TechnicalReportPath(instance, filename):
        return "tech/files_{0}/{1}".format(instance.user.id,filename)
def BugReportPath(instance, filename):
        return "bug/files_{0}/{1}".format(instance.user.id,filename)
def RequestPath(instance, filename):
        return "req/files_{0}/{1}".format(instance.user.id,filename)

def TechnicalImage(instance, filename):
        return "tech/imgs_{0}/{1}".format(instance.user.id,filename)
def BugReportImage(instance,filename):
        return "bug/imgs_{0}/{1}".format(instance.user.id,filename)
def RequestImage(instance, filename):
        return "req/imgs_{0}/{1}".format(instance.user.id,filename)


class TimeStampedModel(models.Model):
        created_at = models.DateTimeField(auto_now_add=True)
        updated_at = models.DateTimeField(auto_now=True)

        class Meta:
                abstract = True

class Members(models.Model):
        name= models.CharField(max_length=20, blank=True)
        position= models.CharField(max_length=20, blank=True)

class WorkSpace(TimeStampedModel):

        creator = models.ForeignKey(User,on_delete=models.CASCADE, related_name='owned_workspaces' )
        members = models.ManyToManyField(User, through='WorkSpaceMember')
        name=models.CharField(max_length=255)
        description=models.TextField()
        is_archived = models.BooleanField(default=False, db_index=True)
        archived_at = models.DateTimeField(null=True, blank=True)
        archived_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True, related_name="archived_workspaces")
        #is_pinned = models.BooleanField(default=False)
        class Meta:
                indexes = [
                        models.Index(fields=['creator']),
                        models.Index(fields=['name']),
                ]

class WorkSpaceMember(models.Model):
        ROLE_CHOICES = [
        ('ADMIN', 'Admin'),
        ('MEMBER', 'Member'), ]
        role = models.CharField(max_length=10, choices=ROLE_CHOICES, default='MEMBER')
        user = models.ForeignKey(User, on_delete=models.CASCADE)
        workspace = models.ForeignKey(WorkSpace, on_delete=models.CASCADE)
        date_joined = models.DateTimeField(auto_now_add=True)
        is_pinned = models.BooleanField(default=False)
        class Meta:
                unique_together = ('user', 'workspace')
                indexes = [
                models.Index(fields=['user']),
                models.Index(fields=['workspace']),
                models.Index(fields=['role']),
        ]

def default_working_days():
        return [
                "MON",
                "TUE",
                "WED",
                "THU",
                "FRI",]
def default_weekly_schedule():
        return {
                        "MON": {"enabled": True, "start": "09:00", "end": "17:00"},
                        "TUE": {"enabled": True, "start": "09:00", "end": "17:00"},
                        "WED": {"enabled": True, "start": "09:00", "end": "17:00"},
                        "THU": {"enabled": True, "start": "09:00", "end": "17:00"},
                        "FRI": {"enabled": True, "start": "09:00", "end": "17:00"},
                        "SAT": {"enabled": True, "start": "09:00", "end": "17:00"},
                        "SUN": {"enabled": True, "start": "09:00", "end": "17:00"},
                }
class WorkspaceWorkingSchedule(models.Model):
        workspace = models.OneToOneField(WorkSpace,on_delete=models.CASCADE,related_name="working_schedule",)

        working_days = models.JSONField(default=default_working_days,help_text="Working days: MON,TUE,WED,THU,FRI,SAT,SUN",)

        start_time = models.TimeField(default="09:00",)

        end_time = models.TimeField(default="17:00",)

        timezone = models.CharField(max_length=50,default="UTC",)

        created_at = models.DateTimeField(auto_now_add=True,)

        updated_at = models.DateTimeField(auto_now=True,)

        is_24_hours = models.BooleanField(default=False,)

        weekly_schedule = models.JSONField(default=default_weekly_schedule,blank=True, )

        def __str__(self):
                return f"{self.workspace.name} schedule"
class Project(TimeStampedModel):
        STATUS_CHOICES = [
        ('pending', 'Pending'),
        ('on_going', 'On Going'),
        ('completed', 'Completed'),]
        workspace=models.ForeignKey(WorkSpace,on_delete=models.CASCADE,null=True,related_name='projects')
        name=models.CharField(null=False,max_length=255)
        deadline = models.DateTimeField(null=True, blank=True)
        description=models.TextField(null=False)
        members = models.ManyToManyField(User, through='ProjectRole')
        status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='pending')
        is_archived = models.BooleanField(default=False, db_index=True)
        archived_at = models.DateTimeField(null=True, blank=True)
        archived_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True, related_name="archived_projects")

        class Meta:
                indexes = [
                        models.Index(fields=["workspace"]),
                        models.Index(fields=["status"]),
                        models.Index(fields=["deadline"]),
                ]

class ProjectRole(models.Model):
        ROLE_CHOICES = [
        ('ADMIN', 'Admin '), ('EMPLOYEE', 'employee'),('MANAGER','Manager'),('VIEWER', 'Viewer') ]
        role = models.CharField(max_length=10, choices=ROLE_CHOICES, default='EMPLOYEE')
        project = models.ForeignKey(Project, on_delete=models.CASCADE)
        user = models.ForeignKey(User, on_delete=models.CASCADE)
        date_joined = models.DateTimeField(auto_now_add=True)
        class Meta:
                unique_together = ('project', 'user')
        indexes = [
                models.Index(fields=['project']),
                models.Index(fields=['user']),
                models.Index(fields=['role']),
        ]

class Task(TimeStampedModel):

        STATUS_CHOICES = [
                ('TODO', 'To Do'),
                ('INPROGRESS', 'In Progress'),
                ('REVIEW', 'Review'),
                ('DONE', 'Done'),
                ("PAUSED", "Paused"),
        ]

        PRIORITY_CHOICES = [
                ('L', 'Low'),
                ('M', 'Medium'),
                ('H', 'High'),
        ]

        TYPE_CHOICES = [
        ('TASK', 'Task'),
        ('BUG', 'Bug'),
        ('FEATURE', 'Feature'),
        ('IMPROVEMENT', 'Improvement')]

        REPORT_CHOICES=[
        ("NONE", "No Report"),
        ("PENDING", "Pending"),
        ("SUBMITTED", "Submitted"),
        ("REJECTED", "Rejected"),
        ("APPROVED", "Approved")]

        ASSIGNMENT_STATE = [
        ('UNASSIGNED_NEW', 'Not Assigned Yet'),
        ('UNASSIGNED_RETURNED', 'Returned / Removed'),
        ('ASSIGNED', 'Assigned'),]

        creator = models.ForeignKey(User, on_delete=models.CASCADE, related_name="created_tasks")
        project = models.ForeignKey(Project, on_delete=models.CASCADE, related_name='tasks')
        priority = models.CharField(max_length=20, choices=PRIORITY_CHOICES, default='M')
        status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='TODO')
        type = models.CharField(max_length=30, choices=TYPE_CHOICES, default="TASK")
        parent = models.ForeignKey("self", null=True, blank=True, on_delete=models.CASCADE, related_name="subtasks")
        title = models.CharField(max_length=200)
        description = models.TextField()
        expected_duration = models.DurationField(verbose_name="Expected Duration")
        actual_duration = models.DurationField( null=True,blank=True,default=timedelta(0),verbose_name="Actual Worked Duration")
        assigned_at = models.DateTimeField(null=True,blank=True)
        link = models.URLField(max_length=500, null=True, blank=True)
        due_date = models.DateTimeField()

        start_time = models.DateTimeField(null=True, blank=True)
        end_time = models.DateTimeField(null=True, blank=True)
        assigned_to = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True, related_name='assigned_tasks')
        report_status = models.CharField(max_length=20,choices=REPORT_CHOICES,default="NONE")
        assignment_state = models.CharField(max_length=20,choices=ASSIGNMENT_STATE,default='UNASSIGNED_NEW')

        is_deleted = models.BooleanField(default=False,db_index=True,)
        is_archived = models.BooleanField(default=False, db_index=True)
        archived_at = models.DateTimeField(null=True, blank=True)
        archived_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True, related_name="archived_tasks")

        deleted_at = models.DateTimeField(null=True,blank=True,)
        deleted_by = models.ForeignKey(
                settings.AUTH_USER_MODEL,
                on_delete=models.SET_NULL,
                null=True,
                blank=True,
                related_name="soft_deleted_tasks",
        )

        def save(self, *args, **kwargs):
                if self.pk is None:
                        if self.assigned_to is None:
                                self.assignment_state = 'UNASSIGNED_NEW'
                        else:
                                self.assignment_state = 'ASSIGNED'
                else:
                        if self.assigned_to is None:
                                self.assignment_state = 'UNASSIGNED_RETURNED'
                        else:
                                self.assignment_state = 'ASSIGNED'

                super().save(*args, **kwargs)

        def is_unassigned(self):
                return self.assignment_state in [
                        'UNASSIGNED_NEW',
                        'UNASSIGNED_RETURNED'
                ]
        @property
        def blocking_dependencies(self):
                return self.task_dependencies.filter(
                        dependency_type="BLOCKS",
                ).exclude(
                        predecessor__status="DONE",
                )


        @property
        def is_blocked(self):
                return self.blocking_dependencies.exists()


        @property
        def can_start(self):
                return (
                        self.status == "TODO"
                        and self.assigned_to_id is not None
                        and not self.is_deleted
                        and not self.is_archived
                        and not self.is_blocked
                )
        class Meta:
                indexes = [
                models.Index(fields=["status"]),
                models.Index(fields=["project"]),
                models.Index(fields=["assigned_to"]),
                ]
                ordering = ["-created_at"]


class TaskImage(TimeStampedModel):
        task = models.ForeignKey(Task, on_delete=models.CASCADE, related_name='images')
        user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='uploaded_task_images')
        image = models.ImageField(upload_to=TaskPhotoPath)


class TaskFile(TimeStampedModel):
        task = models.ForeignKey(Task, on_delete=models.CASCADE, related_name='files')
        user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='uploaded_task_files')
        file = models.FileField(upload_to=TaskFilePath)



class TaskDependency(TimeStampedModel):
        DEPENDENCY_TYPES = [
                ("BLOCKS", "Blocks"),
                ("RELATED", "Related"),
        ]

        predecessor = models.ForeignKey(
                Task,
                on_delete=models.CASCADE,
                related_name="dependent_tasks",
        )

        successor = models.ForeignKey(
                Task,
                on_delete=models.CASCADE,
                related_name="task_dependencies",
        )

        dependency_type = models.CharField(
                max_length=20,
                choices=DEPENDENCY_TYPES,
                default="BLOCKS",
        )

        created_by = models.ForeignKey(
                settings.AUTH_USER_MODEL,
                on_delete=models.SET_NULL,
                null=True,
                related_name="created_task_dependencies",
        )

        class Meta:
                constraints = [
                models.UniqueConstraint(
                        fields=[
                        "predecessor",
                        "successor",
                        "dependency_type",
                        ],
                        name="unique_task_dependency",
                ),
                models.CheckConstraint(
                        condition=~models.Q(
                        predecessor=models.F("successor")
                        ),
                        name="prevent_task_self_dependency",
                ),
                ]

                indexes = [
                models.Index(fields=["predecessor"]),
                models.Index(fields=["successor"]),
                models.Index(fields=["dependency_type"]),
                ]










class TechnicalReportForm(TimeStampedModel):

        QUALITY_CHOICES = [
        ('EXCELLENT', 'Excellent - Fully Compliant'),
        ('GOOD', 'Good - Minor Adjustments Needed'),
        ('AVERAGE', 'Average - Meets Minimum Requirements'),
        ('POOR', 'Poor - Non-Compliant'),
        ('CRITICAL', 'Critical - Urgent Fix Required'),]
        REPORT_STATUS = [
        ('DRAFT', 'Draft'),
        ('SUBMITTED', 'Submitted'),
        ('APPROVED', 'Approved'),
        ('REJECTED', 'Rejected'), ]

        task = models.ForeignKey(Task, on_delete=models.CASCADE, related_name='technical_reports')
        user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='my_technical_reports')
        #
        status = models.CharField(max_length=20, choices=REPORT_STATUS, default='DRAFT')
        #
        image=models.ImageField(upload_to=TechnicalImage,null=True,blank=True)
        file=models.FileField( upload_to=TechnicalReportPath, max_length=100,blank=True, null=True)
        description=models.TextField(null=False)
        duration_time= models.DurationField(null=True, blank=True)
        url=models.URLField(blank=True, null=True)
        #
        quality=models.CharField(choices=QUALITY_CHOICES,max_length=255,null=True)
        manager_feedback = models.TextField(null=True, blank=True)
        manager_feedbacks = models.JSONField(default=list, blank=True)

        class Meta:
                indexes = [
                models.Index(fields=['user']),
                models.Index(fields=['status']),]
                ordering = ['-created_at']


class RequestForm(TimeStampedModel):
        REQUEST_TYPES = [
        ('LEAVE', 'Leave Request '),
        ('RESOURCE', 'Resource Request '),
        ('ACCESS', 'Access Request '),
        ('SUPPORT', 'Technical Support'),
        ('OTHER', 'Other'),]

        PRIORITY_LEVELS = [
        ('LOW', 'Low'),
        ('NORMAL', 'Normal'),
        ('URGENT', 'Urgent'),]

        STATUS_CHOICES = [
        ('PENDING', 'Pending'),
        ('APPROVED', 'Approved'),
        ('REJECTED', 'Rejected'),
        ("ACTION_REQUIRED", "Action Required"),
        ("CANCELLED", "Cancelled"),
        ("COMPLETED", "Completed"),
        ('ON_HOLD', 'On Hold') ]

        user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='requests')
        request_type = models.CharField(max_length=20, choices=REQUEST_TYPES, default='OTHER')
        priority = models.CharField(max_length=10, choices=PRIORITY_LEVELS, default='NORMAL')
        status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='PENDING')
        manager_feedback = models.TextField(blank=True, null=True)
        reason = models.TextField()
        project = models.ForeignKey(Project, on_delete=models.CASCADE, related_name='my_requests')
        title=models.CharField( max_length=220)
        file = models.FileField(upload_to=RequestPath, blank=True, null=True)
        image=models.ImageField(upload_to=RequestImage,null=True,blank=True)
        time=models.DateTimeField()
        requested_at = models.DateTimeField(null=True,blank=True,)
        leave_start = models.DateTimeField(  null=True,blank=True,)
        leave_end = models.DateTimeField(  null=True,blank=True,)

        class Meta:
                indexes = [
                models.Index(fields=['user']),
                models.Index(fields=['project']),
                models.Index(fields=['status']),]
                ordering = ['-created_at']



class LeaveTaskAction(TimeStampedModel):
        ACTION_CHOICES = [
                ("NO_ACTION", "No Action"),
                ("TRANSFER_TASK", "Transfer Task"),
                ("EXTEND_DUE_DATE", "Extend Due Date"),
                ("PAUSE_TASK", "Pause Task"),
                ("REVIEW_REPORT", "Review Report")
        ]

        IMPACT_CHOICES = [
                ("COMPLETED", "Completed"),
                ("NO_DUE_DATE", "No Due Date"),
                (
                        "CAN_FINISH_BEFORE_LEAVE",
                        "Can Finish Before Leave",
                ),
                (
                        "NOT_ENOUGH_TIME_BEFORE_LEAVE",
                        "Not Enough Time Before Leave",
                ),
                (
                        "DUE_DURING_LEAVE",
                        "Due During Leave",
                ),
                (
                        "CAN_FINISH_AFTER_RETURN",
                        "Can Finish After Return",
                ),
                (
                        "NOT_ENOUGH_TIME_AFTER_RETURN",
                        "Not Enough Time After Return",
                ),
                ]

        previous_assignee = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="previous_leave_task_assignments",
        )

        previous_due_date = models.DateTimeField(
        null=True,
        blank=True,
)
        request = models.ForeignKey(RequestForm, on_delete=models.CASCADE, related_name="leave_task_actions")
        task = models.ForeignKey(Task, on_delete=models.CASCADE, related_name="leave_request_actions")
        action = models.CharField(max_length=30, choices=ACTION_CHOICES, blank=True, null=True)
        new_assignee = models.ForeignKey(User, on_delete=models.SET_NULL, blank=True, null=True, related_name="leave_transferred_tasks")
        new_due_date = models.DateTimeField(blank=True, null=True)
        previous_task_status = models.CharField(max_length=30, blank=True, null=True)
        impact = models.CharField(max_length=40, choices=IMPACT_CHOICES)
        requires_action = models.BooleanField(default=False)
        is_resolved = models.BooleanField(default=False)
        resolved_by = models.ForeignKey(User, on_delete=models.SET_NULL, blank=True, null=True, related_name="resolved_leave_task_actions")
        resolved_at = models.DateTimeField(blank=True, null=True)

        class Meta:
                constraints = [
                models.UniqueConstraint(fields=["request", "task"], name="unique_task_per_leave_request"),
                ]

        def __str__(self):
                return f"Leave request {self.request_id} - Task {self.task_id}"



class BugReportForm(TimeStampedModel):
        DANGEROUS_CHOICES=[
                ('LOW','low'), ('MEDIUM','medium'), ('HIGH','high') ]
        BUG_STATUS = [
        ('OPEN', 'Open'),
        ('FIXED', 'Fixed'),
        ('VERIFIED', 'Verified'),
        ('CLOSED', 'Closed'),]
        task = models.ForeignKey(
                Task,
                on_delete=models.SET_NULL,
                related_name="bug_reports",
                null=True,
                blank=True,
                )
        user = models.ForeignKey(User, on_delete=models.CASCADE)
        project = models.ForeignKey(Project, on_delete=models.CASCADE, related_name='bug_reports_task')
        status = models.CharField(max_length=10, choices=BUG_STATUS, default='OPEN')
        dangerous_level=models.CharField(choices=DANGEROUS_CHOICES,max_length=255)
        title=models.CharField( max_length=50)
        assigned_to = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True, related_name='assigned_bugs')
        description=models.TextField(null=False)
        url = models.URLField(blank=True, null=True)
        file = models.FileField(upload_to=BugReportPath, blank=True, null=True)
        image=models.ImageField(upload_to=BugReportImage,null=True,blank=True)
        result=models.TextField(null=True,blank=True)

        class Meta:
                indexes = [
                        models.Index(fields=['user']),
                        models.Index(fields=['project']),
                        models.Index(fields=['status']),
                ]
                ordering = ['-created_at']


class BugTaskLink(TimeStampedModel):
        bug = models.ForeignKey(
                BugReportForm,
                on_delete=models.CASCADE,
                related_name="task_links",
        )

        task = models.OneToOneField(
                Task,
                on_delete=models.CASCADE,
                related_name="bug_link",
        )

        created_by = models.ForeignKey(
                settings.AUTH_USER_MODEL,
                on_delete=models.SET_NULL,
                null=True,
                related_name="created_bug_task_links",
        )

        class Meta:
                constraints = [
                models.UniqueConstraint(
                        fields=["bug", "task"],
                        name="unique_bug_task_link",
                )
                ]

class Invitation(TimeStampedModel):
        ROLE_CHOICES = [
        ('ADMIN', 'Admin'),
        ('DEV', 'Developer'),
        ('EMPLOYEE', 'Employee'),
        ('MANAGER', 'Manager'),]

        STATUS_CHOICES = [
        ('PENDING', 'Pending'),
        ('ACCEPTED', 'Accepted'),
        ('REJECTED', 'Rejected'),]

        sender = models.ForeignKey(User, related_name='sent_invitations', on_delete=models.CASCADE)
        receiver = models.ForeignKey(User, on_delete=models.CASCADE, null=True, blank=True)
        receiver_email = models.EmailField()
        workspace = models.ForeignKey(WorkSpace, on_delete=models.CASCADE, null=False, blank=True)
        project = models.ForeignKey(Project, on_delete=models.CASCADE, null=True, blank=True)
        role = models.CharField(max_length=20,null=True,   choices=ROLE_CHOICES ,default='EMPLOYEE')
        status = models.CharField(max_length=10, choices=STATUS_CHOICES, default='PENDING')

        class Meta:
                indexes = [
                        models.Index(fields=['receiver_email']),
                        models.Index(fields=['workspace']),
                        models.Index(fields=['project']),
                        models.Index(fields=['status']),
                ]
                ordering = ['-created_at']














#######################################################################################
class Notification(TimeStampedModel):
        NOTIFICATION_TYPES = [
        ('TASK_ASSIGNED', 'Task Assigned'),
        ('TASK_UNASSIGNED', 'TASK_UNASSIGNED'),
        ('SYSTEM_ALERT', 'System Alert'),
        ('COMMENT_ADDED', 'New Comment'),
        ('REPORT_REJECTED', 'Report Rejected'),
        ('REPORT_SUBMITTED', 'Report Submitted'),
        ('INVITATION_RECEIVED', 'Invitation Received'),
        ('INVITATION_ACCEPTED', 'Invitation Accepted'),
        ('INVITATION_REJECTED', 'Invitation Rejected'),
        ('BUG_REPORTED', 'Bug Reported'),
        ('BUG_CLOSED', 'Bug Closed'),
        ('BUG_CONVERTED_TO_TASK', 'Bug Converted To Task'),
        ]
        recipient = models.ForeignKey(User, on_delete=models.CASCADE, related_name='notifications')
        notification_type = models.CharField(max_length=30, choices=NOTIFICATION_TYPES, default='SYSTEM_ALERT')
        title = models.CharField(max_length=255)
        message = models.TextField()
        is_read = models.BooleanField(default=False)
        navigation_target = models.CharField(max_length=255, null=True, blank=True)
        class Meta:
                ordering = ['-created_at']


class ActivityLog(TimeStampedModel):
        ActionTypes=[
        ('ACCOUNT_CREATED','account created'),
        ('WORKSPACE_CREATED', 'Workspace Created'),
        ('WORKSPACE_UPDATED', 'Workspace Updated'),
        ('WORKSPACE_DELETED', 'Workspace Deleted'),
        ('WORKSPACE_LEFT', 'Workspace Left'),
        ('WORKSPACE_OWNERSHIP_TRANSFERRED', 'Workspace Ownership Transferred'),
        ('PROJECT_CREATED', 'Project Created'),
        ('PROJECT_UPDATED', 'Project Updated'),
        ('PROJECT_DELETED', 'Project Deleted'),
        ('PROJECT_LEFT', 'Project Left'),
        ('TASK_ASSIGNED', 'Task Assigned'),
        ('TASK_UNASSIGNED', 'Task Unassigned'),
        ('TASK_DELETED', 'Task Deleted'),
        ('MEMBER_ADDED', 'User Added'),
        ('MEMBER_REMOVED', 'User Removed from Workspace'),
        ('MEMBER_LEFT', 'User left from Workspace'),
        ('ACCOUNT_PURGED', 'Account Deleted'),
        ('GENERAL_UPDATE','General update'),
        ('REPORT_REVIEWED', 'Report Reviewed'),
        ('INVITATION_SENT', 'Invitation Sent'),
        ('INVITATION_ACCEPTED', 'Invitation Accepted'),
        ('INVITATION_REJECTED', 'Invitation Rejected'),

        ('REQUEST_CREATED', 'Request Created'),
        ('REQUEST_UPDATED', 'Request Updated'),
        ('REQUEST_DELETED', 'Request Deleted'),
        ('REQUEST_REVIEWED', 'Request Reviewed'),

        ('REPORT_DRAFT_CREATED', 'Report Draft Created'),
        ('REPORT_DRAFT_UPDATED', 'Report Draft Updated'),
        ('REPORT_DELETED', 'Report Deleted'),
        ('REPORT_SUBMITTED', 'Report Submitted'),
        ('BUG_REPORTED', 'Bug Reported'),
        ('BUG_UPDATED', 'Bug Updated'),
        ('BUG_DELETED', 'Bug Deleted'),
        ('BUG_CONVERTED_TO_TASK', 'Bug Converted To Task'),
        ('ROLE_UPDATED','Role Updated'),
        ('BULK_TASK_UPDATED', 'Bulk Task Updated'),
        ('WORKSPACE_ARCHIVED', 'Workspace Archived'),
        ('WORKSPACE_RESTORED', 'Workspace Restored'),
        ('PROJECT_ARCHIVED', 'Project Archived'),
        ('PROJECT_RESTORED', 'Project Restored'),
        ('TASK_ARCHIVED', 'Task Archived'),
        ('TASK_RESTORED', 'Task Restored')

        ]
        user=models.ForeignKey(User,on_delete=models.CASCADE)
        action = models.CharField(max_length=100,choices=ActionTypes,default='GENERAL_UPDATE')
        action_id=models.PositiveIntegerField()
        changes=models.JSONField(default=dict)

class TaskComment(TimeStampedModel):
        task = models.ForeignKey(Task, on_delete=models.CASCADE, related_name='comments')
        user = models.ForeignKey(User, on_delete=models.CASCADE)
        content = models.TextField()
        file = models.FileField(upload_to=CommentAttachmentPath, null=True, blank=True)


