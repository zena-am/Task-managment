from django.db import models
from django.shortcuts import render
from django.contrib.auth.models import AbstractUser
from django.db import models
from django.utils.text import slugify
import uuid

class User(AbstractUser):
        email=models.EmailField(unique=True)
        mfa_secret = models.CharField(max_length=200, blank=True, null=True)
        mfa_enabled = models.BooleanField(default=False)

def ProfileImage(instance,filename):
        return "/avatar_{0}/{1}".format(instance.user.id,filename)
def BugReportImage(instance,filename):
        return "/BugReportImage_{0}/{1}".format(instance.user.id,filename)
def get_default_user():
        return User.objects.get_or_create(username='default_user')[0]


class Members(models.Model):
        name= models.CharField(max_length=20, blank=True)
        position= models.CharField(max_length=20, blank=True)


class WorkSpace(models.Model):
        members = models.ManyToManyField(User, through='WorkSpaceMember')
        name=models.CharField(max_length=255)
        date=models.DateTimeField(auto_now_add=True)
        to_date=models.DateTimeField(auto_now=True)
        discription=models.TextField()
        icon_name = models.CharField(max_length=50, default='default_icon')

class WorkSpaceMember(models.Model):
        user = models.ForeignKey(User, on_delete=models.CASCADE)
        workspace = models.ForeignKey(WorkSpace, on_delete=models.CASCADE)
        position = models.CharField(max_length=50, blank=True)
        date_joined = models.DateTimeField(auto_now_add=True)
        class Meta:
                unique_together = ('user', 'workspace')

class Project(models.Model):
        workSpace=models.ForeignKey(WorkSpace,on_delete=models.CASCADE)
        name=models.CharField(null=False,max_length=255)
        created_at=models.DateTimeField(auto_now_add=True)
        to_date=models.DateTimeField(auto_now=True)
        discription=models.TextField(null=False)
        members = models.ManyToManyField(User, through='ProjectRole')


class ProjectRole(models.Model):
        ROLE_CHOICES = [
        ('ADMIN', 'Project Manager'), ('DEV', 'Developer'),('EMPLOYEE', 'employee'), ]
        role = models.CharField(max_length=10, choices=ROLE_CHOICES, default='EMPLOYEE')
        project = models.ForeignKey(Project, on_delete=models.CASCADE)
        user = models.ForeignKey(User, on_delete=models.CASCADE)
        date_joined = models.DateTimeField(auto_now_add=True)
        class Meta:
                unique_together = ('project', 'user')


class Task(models.Model):
        STATUS_CHOICES=[ ('TODO','to do'), ('INPROGRESS','in progress'), ('DONE','done') ]
        PRIORITY_CHOICES = [('L', 'Low'), ('M', 'Medium'), ('H', 'High')]
        priority = models.CharField(max_length=1, choices=PRIORITY_CHOICES, default='M')
        status=models.CharField(max_length=256,choices=STATUS_CHOICES,default='TODO')
        title = models.CharField(max_length=200)
        time_expected= models.DurationField()
        actual_duration = models.DurationField(null=True, blank=True)
        strat_time=models.DateTimeField(null=False,auto_now_add=True)
        end_time=models.DateTimeField(null=True,blank=True,auto_now=True)
        extra_data = models.JSONField(default=dict, blank=True)
        supervisor = models.ForeignKey(User, on_delete=models.SET(get_default_user),related_name='supervised_tasks')
        assigned_to = models.ForeignKey(User, on_delete=models.SET_NULL, null=True,related_name='assigned_tasks')

class ActivityLog(models.Model):
        user=models.ForeignKey(User,on_delete=models.CASCADE)
        action = models.CharField(max_length=100)
        action_id=models.PositiveIntegerField()
        changes=models.JSONField(default=dict)
        created_at=models.DateTimeField(auto_now_add=True)

class Profile(models.Model):
        user = models.OneToOneField(User, on_delete=models.CASCADE)
        avatar = models.ImageField(upload_to=ProfileImage, null=True, blank=True)
        phone = models.CharField(max_length=20, blank=True)
        position = models.CharField(max_length=50, blank=True)
        bio = models.TextField(max_length=500, blank=True)
        slug = models.SlugField(unique=True,null=True, blank=True)
        def save(self, *args, **kwargs):
                if not self.slug:

                        base_slug = slugify(self.user.username)
                        self.slug = f"{base_slug}-{str(uuid.uuid4())[:8]}"
                super().save(*args, **kwargs)

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
        author = models.ForeignKey(User, on_delete=models.CASCADE, related_name='my_technical_reports')
        quality=models.CharField(choices=QUALITY_CHOICES,max_length=255)
        status = models.CharField(max_length=20, choices=REPORT_STATUS, default='DRAFT')
        url=models.URLField()
        image=models.ImageField(BugReportImage,null=True,blank=True)
        discription=models.TextField(null=False)
        duation_time= models.DurationField(null=True, blank=True)
        file=models.FileField( upload_to=None, max_length=100)
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
        status = models.CharField(max_length=10, choices=BUG_STATUS, default='OPEN')
        dangerous_level=models.CharField(choices=DANGEROUS_CHOICES,max_length=255)
        title=models.CharField( max_length=50)
        project = models.ForeignKey(Project, on_delete=models.CASCADE, related_name='bugs')
        reported_by = models.ForeignKey(User, on_delete=models.CASCADE, related_name='reported_bugs')
        assigned_to = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True, related_name='assigned_bugs')
        discription=models.TextField(null=False)
        url = models.URLField(blank=True, null=True)
        file = models.FileField(upload_to='bugs/logs/', blank=True, null=True)
        image=models.ImageField(BugReportImage,null=True,blank=True)
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
        request_type = models.CharField(max_length=20, choices=REQUEST_TYPES, default='OTHER')
        priority = models.CharField(max_length=10, choices=PRIORITY_LEVELS, default='NORMAL')
        status = models.CharField(max_length=10, choices=STATUS_CHOICES, default='PENDING')
        manager_feedback = models.TextField(blank=True, null=True)
        reason = models.TextField()
        project = models.ForeignKey(Project, on_delete=models.CASCADE, related_name='my_requests')
        title=models.CharField( max_length=220)
        created_at = models.DateTimeField(auto_now_add=True)
        time=models.DateTimeField()

#######################################################################################
class NotificationPreference(models.Model):
        user = models.ForeignKey(User, on_delete=models.CASCADE)
        project = models.ForeignKey(Project, on_delete=models.CASCADE)
        level = models.PositiveSmallIntegerField(default=1)