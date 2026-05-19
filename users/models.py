from django.db import models
from django.shortcuts import render
from django.contrib.auth.models import AbstractUser
from django.db import models
from django.utils.text import slugify
from django.contrib.auth.hashers import make_password
from django.core.validators import RegexValidator
from .error_messages import PHONE_VALIDATION_ERROR
import uuid

class User(AbstractUser):
        email=models.EmailField(unique=True)
        avatar = models.ImageField(upload_to="profiles/", null=True, blank=True)
        phone = models.CharField(max_length=20, blank=True)

        phone_regex = RegexValidator(
        regex=r"^\+?1?\d{9,15}$",
        message=PHONE_VALIDATION_ERROR
)
        @property
        def profile_data(self):
                return {
                "full_name": f"{self.first_name} {self.last_name}".strip() or self.username,
                "image": self.avatar.url if self.avatar else None,
                "phone": self.phone}

def get_default_user():
        user, created = User.objects.get_or_create(
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




class Members(models.Model):
        name= models.CharField(max_length=20, blank=True)
        position= models.CharField(max_length=20, blank=True)


class WorkSpace(models.Model):

        creator = models.ForeignKey(User,on_delete=models.CASCADE, related_name='owned_workspaces' )
        members = models.ManyToManyField(User, through='WorkSpaceMember')
        name=models.CharField(max_length=255)
        created_at=models.DateTimeField(auto_now_add=True)
        updated_at=models.DateTimeField(auto_now=True)
        description=models.TextField()
        is_pinned = models.BooleanField(default=False)

class WorkSpaceMember(models.Model):
        ROLE_CHOICES = [
        ('ADMIN', 'Admin '), ('DEV', 'Developer'),('EMPLOYEE', 'employee'),('MANAGER','Manager') ]
        role = models.CharField(max_length=10, choices=ROLE_CHOICES, default='EMPLOYEE')
        user = models.ForeignKey(User, on_delete=models.CASCADE)
        workspace = models.ForeignKey(WorkSpace, on_delete=models.CASCADE)
        date_joined = models.DateTimeField(auto_now_add=True)
        is_pinned = models.BooleanField(default=False)
        class Meta:
                unique_together = ('user', 'workspace')

class Project(models.Model):
        STATUS_CHOICES = [
        ('pending', 'Pending'),
        ('on_going', 'On Going'),
        ('completed', 'Completed'),]
        workspace=models.ForeignKey(WorkSpace,on_delete=models.CASCADE,null=True,related_name='projects')
        name=models.CharField(null=False,max_length=255)
        created_at=models.DateTimeField(auto_now_add=True)
        updated_at=models.DateTimeField(auto_now=True)
        deadline = models.DateTimeField(null=True, blank=True)
        description=models.TextField(null=False)
        members = models.ManyToManyField(User, through='ProjectRole')
        status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='pending')


class ProjectRole(models.Model):
        ROLE_CHOICES = [
        ('ADMIN', 'Admin '), ('DEV', 'Developer'),('EMPLOYEE', 'employee'),('MANAGER','Manager') ]
        role = models.CharField(max_length=10, choices=ROLE_CHOICES, default='EMPLOYEE')
        project = models.ForeignKey(Project, on_delete=models.CASCADE)
        user = models.ForeignKey(User, on_delete=models.CASCADE)
        date_joined = models.DateTimeField(auto_now_add=True)
        class Meta:
                unique_together = ('project', 'user')


class Task(models.Model):
        STATUS_CHOICES=[ ('UNASSIGNED','unassigned'),('TODO','to do'), ('INPROGRESS','in progress'), ('DONE','done') ]
        PRIORITY_CHOICES = [('L', 'Low'), ('M', 'Medium'), ('H', 'High')]
        user = models.ForeignKey(User, on_delete=models.CASCADE)
        project = models.ForeignKey(Project, on_delete=models.CASCADE, related_name='tasks')
        priority = models.CharField(max_length=1, choices=PRIORITY_CHOICES, default='M',null=False)
        status=models.CharField(max_length=256,choices=STATUS_CHOICES,default='TODO')
        title = models.CharField(max_length=200,null=False)
        description=models.TextField(null=False)
        time_expected= models.DurationField(null=False)
        actual_duration = models.DurationField(null=True, blank=True)
        start_time=models.DateTimeField(null=True,blank=True)
        end_time=models.DateTimeField(null=True,blank=True)
        image = models.ImageField(upload_to=TaskPhotoPath, null=True, blank=True)
        file = models.FileField(upload_to=TaskFilePath, null=True, blank=True)
        link = models.URLField(max_length=500, null=True, blank=True)
        created_at=models.DateTimeField(auto_now_add=True)
        updated_at=models.DateTimeField(auto_now=True)
        due_date=models.DateTimeField(null=False,blank=True)
        assigned_to = models.ForeignKey(User, on_delete=models.SET_NULL, null=True,related_name='assigned_tasks')
        supervisor = models.ForeignKey(User, on_delete=models.SET(get_default_user),related_name='supervised_tasks')








class TechnicalReportForm(models.Model):
        STATUS_CHOICES=[
                ('TODO','to do'), ('INPROGRESS','in progress'), ('DONE','done')
        ]
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
        user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='my_technical_reports')
        quality=models.CharField(choices=QUALITY_CHOICES,max_length=255)
        status = models.CharField(max_length=20, choices=REPORT_STATUS, default='DRAFT')
        image=models.ImageField(upload_to=TechnicalImage,null=True,blank=True)
        file=models.FileField( upload_to=TechnicalReportPath, max_length=100)
        discription=models.TextField(null=False)
        duation_time= models.DurationField(null=True, blank=True)
        url=models.URLField()
        created_at = models.DateTimeField(auto_now_add=True)
        updated_at = models.DateTimeField(auto_now=True)

class BugReportForm(models.Model):
        DANGEROUS_CHOICES=[
                ('LOW','low'), ('MEDIUM','medium'), ('HIGH','high') ]
        BUG_STATUS = [
        ('OPEN', 'Open'),
        ('FIXED', 'Fixed'),
        ('VERIFIED', 'Verified'),
        ('CLOSED', 'Closed'),]
        user = models.ForeignKey(User, on_delete=models.CASCADE)
        status = models.CharField(max_length=10, choices=BUG_STATUS, default='OPEN')
        dangerous_level=models.CharField(choices=DANGEROUS_CHOICES,max_length=255)
        title=models.CharField( max_length=50)
        project = models.ForeignKey(Project, on_delete=models.CASCADE, related_name='bugs')
        assigned_to = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True, related_name='assigned_bugs')
        discription=models.TextField(null=False)
        url = models.URLField(blank=True, null=True)
        file = models.FileField(upload_to=BugReportPath, blank=True, null=True)
        image=models.ImageField(upload_to=BugReportImage,null=True,blank=True)
        result=models.TextField()
        created_at = models.DateTimeField(auto_now_add=True)
        updated_at = models.DateTimeField(auto_now=True)

class RequestForm(models.Model):
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
        ('REJECTED', 'Rejected'), ]
        user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='reported_bugs')
        request_type = models.CharField(max_length=20, choices=REQUEST_TYPES, default='OTHER')
        priority = models.CharField(max_length=10, choices=PRIORITY_LEVELS, default='NORMAL')
        status = models.CharField(max_length=10, choices=STATUS_CHOICES, default='PENDING')
        manager_feedback = models.TextField(blank=True, null=True)
        reason = models.TextField()
        project = models.ForeignKey(Project, on_delete=models.CASCADE, related_name='my_requests')
        title=models.CharField( max_length=220)
        created_at = models.DateTimeField(auto_now_add=True)
        file = models.FileField(upload_to=RequestPath, blank=True, null=True)
        image=models.ImageField(upload_to=RequestImage,null=True,blank=True)
        time=models.DateTimeField()





class Invitation(models.Model):
        STATUS_CHOICES = [
        ('PENDING', 'Pending'),
        ('ACCEPTED', 'Accepted'),
        ('REJECTED', 'Rejected'),]

        sender = models.ForeignKey(User, related_name='sent_invitations', on_delete=models.CASCADE)
        receiver = models.ForeignKey(User, on_delete=models.CASCADE, null=True, blank=True)
        receiver_email = models.EmailField()
        workspace = models.ForeignKey(WorkSpace, on_delete=models.CASCADE, null=False, blank=True)
        project = models.ForeignKey(Project, on_delete=models.CASCADE, null=True, blank=True)
        role = models.CharField(max_length=20, default='EMPLOYEE')
        status = models.CharField(max_length=10, choices=STATUS_CHOICES, default='PENDING')
        created_at = models.DateTimeField(auto_now_add=True)
        project = models.ForeignKey(Project, on_delete=models.CASCADE, null=True, blank=True)
#######################################################################################
class Notification(models.Model):
        NOTIFICATION_TYPES = [
        ('TASK_ASSIGNED', 'Task Assigned'),
        ('TASK_UNASSIGNED', 'TASK_UNASSIGNED'),
        ('SYSTEM_ALERT', 'System Alert'),
        ('COMMENT_ADDED', 'New Comment'),
        ]
        recipient = models.ForeignKey(User, on_delete=models.CASCADE, related_name='notifications')
        notification_type = models.CharField(max_length=20, choices=NOTIFICATION_TYPES, default='SYSTEM_ALERT')
        title = models.CharField(max_length=255)
        message = models.TextField()
        is_read = models.BooleanField(default=False)
        created_at = models.DateTimeField(auto_now_add=True)
        navigation_target = models.CharField(max_length=255, null=True, blank=True)
        class Meta:
                ordering = ['-created_at']


class ActivityLog(models.Model):
        ActionTypes=[
        ('ACCOUNT_CREATED','account created'),
        ('TASK_UNASSIGNED', 'Task Unassigned'),
        ('MEMBER_REMOVED', 'User Removed from Workspace'),
        ('MEMBER_LEFT', 'User left from Workspace'),
        ('ACCOUNT_PURGED', 'Account Deleted'),('GENERAL_UPDATE','General update')
        ]
        user=models.ForeignKey(User,on_delete=models.CASCADE)
        action = models.CharField(max_length=100,choices=ActionTypes,default='GENERAL_UPDATE')
        action_id=models.PositiveIntegerField()
        changes=models.JSONField(default=dict)
        created_at=models.DateTimeField(auto_now_add=True)

class TaskComment(models.Model):
        task = models.ForeignKey(Task, on_delete=models.CASCADE, related_name='comments')
        user = models.ForeignKey(User, on_delete=models.CASCADE)
        content = models.TextField()
        created_at = models.DateTimeField(auto_now_add=True)
        file = models.FileField(upload_to=CommentAttachmentPath, null=True, blank=True)
