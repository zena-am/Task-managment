from datetime import timedelta
from django.utils import timezone
from rest_framework import serializers
from users.serializers.user import UserSerializer
from ..models import Project, ProjectRole, Task,TaskImage,TaskFile, TechnicalReportForm, User


class TaskImageSerializer(serializers.ModelSerializer):
    image_url = serializers.SerializerMethodField()

    class Meta:
        model = TaskImage
        fields = ['id', 'image', 'image_url', 'created_at']

    def get_image_url(self, obj):
        if not obj.image:
            return None

        request = self.context.get('request')
        url = obj.image.url

        if request:
            return request.build_absolute_uri(url)

        return url


class TaskFileSerializer(serializers.ModelSerializer):
    file_url = serializers.SerializerMethodField()
    file_name = serializers.SerializerMethodField()
 
    class Meta:
        model = TaskFile
        fields = ['id', 'file', 'file_url', 'file_name', 'created_at']

    def get_file_url(self, obj):
        if not obj.file:
            return None

        request = self.context.get('request')
        url = obj.file.url

        if request:
            return request.build_absolute_uri(url)

        return url

    def get_file_name(self, obj):
        if not obj.file:
            return None

        return obj.file.name.split('/')[-1]

class TaskSerializer(serializers.ModelSerializer):
    priority_display = serializers.CharField(source='get_priority_display', read_only=True)
    status_display = serializers.CharField(source='get_status_display', read_only=True)
    permissions = serializers.SerializerMethodField()
    assigned_to_detail = UserSerializer(source='assigned_to', read_only=True)
    supervisors_detail = serializers.SerializerMethodField()
    supervisors = serializers.SerializerMethodField()
    time_expected_hours = serializers.SerializerMethodField()
    actual_duration_hours = serializers.SerializerMethodField()
    is_overdue=serializers.SerializerMethodField()
    images = TaskImageSerializer(many=True, read_only=True)
    files = TaskFileSerializer(many=True, read_only=True)
    task_actions = serializers.SerializerMethodField()
    state_label = serializers.SerializerMethodField()
    role_in_project = serializers.SerializerMethodField()
    class Meta:
        model = Task
        fields = [
            'id', 'title', 'project', 'status', 'status_display', 'priority', 'priority_display',
            'expected_duration', 'time_expected_hours', 'actual_duration', 'actual_duration_hours',
            'start_time', 'end_time', 'link','due_date','permissions','state_label','task_actions','role_in_project',
            'assigned_to', 'assigned_to_detail','supervisors_detail', 'supervisors',  'is_overdue','images','files'
        ]

        read_only_fields = ['start_time', 'end_time']
    def get_role_in_project(self, obj):
        request = self.context.get("request")
        user = request.user if request else None

        if not user:
            return None

        role = obj.project.projectrole_set.filter(user=user).values_list("role", flat=True).first()

        return role

    def get_task_actions(self, obj):
        request = self.context.get("request")
        user = request.user if request else None

        if not user or not user.is_authenticated:
            return {}

        is_assigned = obj.assigned_to_id == user.id

        is_manager = obj.project.projectrole_set.filter(
            user=user,
            role__in=["ADMIN", "MANAGER"]
        ).exists()

        is_creator = obj.project.workspace.creator_id == user.id

        return {
            "can_start": is_assigned and obj.status == "TODO",
            "can_pause": is_assigned and obj.status == "INPROGRESS",
            "can_send_to_review": is_assigned and obj.status == "INPROGRESS",
            "can_mark_done_directly": is_manager,
            "can_reassign": is_manager,
            "can_mark_done_directly": is_manager,

            "can_change_status":   is_assigned,
        }
    def get_permissions(self, obj):
        request = self.context.get('request')
        user = request.user if request else None

        if not user or not user.is_authenticated:
            return {
                "can_view": False,
                "can_update": False,
                "can_delete": False,
                "can_assign": False,
                "can_submit_report": False,
            }

        is_assigned = obj.assigned_to_id == user.id

        is_supervisor = obj.project.projectrole_set.filter(
            user=user,
            role__in=["ADMIN", "MANAGER"]
        ).exists()

        is_owner = obj.project.workspace.creator_id == user.id
        is_viewer = obj.project.projectrole_set.filter(user=user,role="VIEWER").exists()

        return {
            "can_view": is_assigned or is_supervisor or is_owner  or is_viewer,
            "can_update": is_assigned,
            "can_delete": is_owner or is_supervisor,
            "can_assign": is_supervisor,
            "can_submit_report": self.requires_report(obj, user) and is_assigned
        }

    def get_state_label(self, obj):
        if obj.status == "TODO":
            return "READY"
        elif obj.status == "INPROGRESS":
            return "ACTIVE"
        elif obj.status == "REVIEW":
            return "WAITING_REVIEW"
        elif obj.status == "DONE":
            return "COMPLETED"
    def get_supervisors_detail(self, obj):
        managers = User.objects.filter(
            projectrole__project=obj.project,
            projectrole__role='MANAGER'
        )
        return UserSerializer(managers, many=True).data
#######################################################################################
    def get_time_expected_hours(self, obj):
        if obj.expected_duration:
            return obj.expected_duration.total_seconds() / 3600
        return 0

    def get_actual_duration_hours(self, obj):
        if obj.actual_duration:
            return obj.actual_duration.total_seconds() / 3600
        return None


    def get_is_overdue(self, obj):
        if obj.status == 'DONE':
            return False

        if obj.start_time and obj.expected_duration:
            deadline = obj.start_time +obj.expected_duration
            return timezone.now() > deadline

        if not obj.start_time and obj.created_at and obj.expected_duration:
            deadline_from_creation = obj.created_at + obj.expected_duration
            return timezone.now() > deadline_from_creation

        return False
    def get_supervisors(self, obj):
            """
            return User.objects.filter(
                projectrole__project=obj.project,
                projectrole__role='MANAGER'
            ).values('username')
"""
            return User.objects.filter(
                    projectrole__project=obj.project,
                    projectrole__role='MANAGER'
                ).values_list('id', flat=True)

    def requires_report(self, obj, user):
        role = ProjectRole.objects.filter(
            project=obj.project,
            user=user
        ).values_list('role', flat=True).first()

        return role == "EMPLOYEE" and obj.assigned_to_id == user.id

    ###########################################################################################################



class TaskCreateUpdateSerializer(serializers.ModelSerializer):
    image_files = serializers.ListField(child=serializers.ImageField(), write_only=True, required=False)
    document_files = serializers.ListField(child=serializers.FileField(), write_only=True, required=False)
    due_date = serializers.DateTimeField(
        input_formats=["%d-%m-%Y", "%d/%m/%Y", "%Y-%m-%d", "%Y-%m-%dT%H:%M:%S%z", "iso-8601"]
    )

    class Meta:
        model = Task
        fields = [
            'id', 'project', 'title', 'description', 'priority', 'status',
            'expected_duration', 'link', 'assigned_to', 'image_files',
            'document_files', 'due_date'
        ]
        read_only_fields = ['id']

    def validate(self, data):
        expected_duration = data.get('expected_duration')
        if expected_duration and expected_duration.total_seconds() <= 0:
            raise serializers.ValidationError({"expected_duration": "it must be greater than 0"})

        project = data.get('project') or getattr(self.instance, 'project', None)
        assignee = data.get('assigned_to')
        if project and assignee:
            is_member = ProjectRole.objects.filter(project=project, user=assignee).exists()
            if not is_member:
                raise serializers.ValidationError(
                    {"assigned_to": "لا يمكن إسناد المهمة لهذا المستخدم لأنه ليس عضواً في هذا المشروع."}
                )
        return data

    def create(self, validated_data):
        image_files = validated_data.pop('image_files', [])
        document_files = validated_data.pop('document_files', [])
        request = self.context.get('request')

        task = Task.objects.create(**validated_data)

        for image in image_files:
            TaskImage.objects.create(task=task, user=request.user, image=image)

        for file in document_files:
            TaskFile.objects.create(task=task, user=request.user, file=file)

        return task

    def update(self, instance, validated_data):
        image_files = validated_data.pop('image_files', [])
        document_files = validated_data.pop('document_files', [])
        request = self.context.get('request')

        for attr, value in validated_data.items():
            setattr(instance, attr, value)
        instance.save()

        for image in image_files:
            TaskImage.objects.create(task=instance, user=request.user, image=image)

        for file in document_files:
            TaskFile.objects.create(task=instance, user=request.user, file=file)

        return instance
#######################################################################################################
class ManagerReportReviewSerializer(serializers.ModelSerializer):
        feedback_text = serializers.CharField(write_only=True, required=False, allow_blank=True)
        class Meta:
            model = TechnicalReportForm
            fields = ['status', 'quality', 'feedback_text','manager_feedbacks','description']
            extra_kwargs = {
            'manager_feedbacks': {'read_only': True},
            'description': {'read_only': True}
        }



class TechnicalReportDetailSerializer(serializers.ModelSerializer):
    employee_name = serializers.SerializerMethodField()
    task_title = serializers.CharField(source="task.title", read_only=True)
    class Meta:
        model = TechnicalReportForm
        fields =[
            'id',
            'task',
            'task_title',
            'employee_name',
            'status',
            'description',
            'duration_time',
            'url',
            'image',
            'file',
            'quality',
            'manager_feedback',
            'manager_feedbacks',
        ]
    def get_employee_name(self, obj):
        return obj.user.get_full_name() or obj.user.username





class ProjectWithoutManagerSerializer(serializers.ModelSerializer):
    workspace_name = serializers.CharField(
        source="workspace.name",
        read_only=True
    )

    members_count = serializers.SerializerMethodField()
    tasks_count = serializers.SerializerMethodField()
    unassigned_tasks_count = serializers.SerializerMethodField()

    class Meta:
        model = Project
        fields = [
            "id",
            "name",
            "workspace_id",
            "workspace_name",
            "members_count",
            "tasks_count",
            "unassigned_tasks_count",
            "created_at"
        ]

    def get_members_count(self, obj):
        return ProjectRole.objects.filter(project=obj).count()

    def get_tasks_count(self, obj):
        return obj.tasks.count()

    def get_unassigned_tasks_count(self, obj):
        return obj.tasks.filter(
            assigned_to__isnull=True
        ).count()