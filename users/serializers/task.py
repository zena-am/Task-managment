from datetime import timedelta
from django.utils import timezone
from rest_framework import serializers
from users.serializers.user import UserSerializer
from ..models import Project, ProjectRole, Task, TaskDependency,TaskImage,TaskFile, TechnicalReportForm, User


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
    assigned_to_detail = serializers.SerializerMethodField()
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
    deleted_by_name = serializers.SerializerMethodField()
    is_blocked = serializers.BooleanField(
    read_only=True,
)

    can_start = serializers.BooleanField(
        read_only=True,
    )

    blocked_by = serializers.SerializerMethodField()
    dependencies = serializers.SerializerMethodField()
    dependents = serializers.SerializerMethodField()

    class Meta:
        model = Task
        fields = [
            'blocked_by',
            'is_blocked' ,
            'can_start',
            "is_deleted",
            "deleted_at",
            "deleted_by",
            "deleted_by_name",
            'id', 'title', 'project', 'status', 'status_display', 'priority', 'priority_display',
            'expected_duration', 'time_expected_hours', 'actual_duration', 'actual_duration_hours',
            'start_time', 'end_time', 'link','due_date','permissions','state_label','task_actions','role_in_project',
            'assigned_to', 'assigned_to_detail','supervisors_detail', 'supervisors',  'is_overdue','images','files',
            'dependencies',
                'dependents',
        ]

        read_only_fields = ['start_time', 'end_time']
    def get_dependencies(self, obj):
        relations = obj.task_dependencies.select_related(
            "predecessor",
        )

        return [
            {
                "dependency_id": relation.id,
                "task_id": relation.predecessor_id,
                "title": relation.predecessor.title,
                "status": relation.predecessor.status,
                "dependency_type": relation.dependency_type,
                "is_completed": (
                    relation.predecessor.status == "DONE"
                ),
            }
            for relation in relations
        ]
    def get_dependents(self, obj):
        relations = obj.dependent_tasks.select_related(
            "successor",
        )

        return [
            {
                "dependency_id": relation.id,
                "task_id": relation.successor_id,
                "title": relation.successor.title,
                "status": relation.successor.status,
                "dependency_type": relation.dependency_type,
            }
            for relation in relations
        ]
    def get_blocked_by(self, obj):
        dependencies = obj.blocking_dependencies.select_related(
            "predecessor",
        )


        return [
            {
                "dependency_id": dependency.id,
                "task_id": dependency.predecessor_id,
                "title": dependency.predecessor.title,
                "status": dependency.predecessor.status,
            }
            for dependency in dependencies
        ]
    def get_deleted_by_name(self, obj):
        if not obj.deleted_by:
            return None

        return (
            obj.deleted_by.get_full_name()
            or obj.deleted_by.username
        )
    def get_assigned_to_detail(self, obj):
        if not obj.assigned_to:
            return None
        return UserSerializer(obj.assigned_to, context=self.context).data

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
                role__in=["ADMIN", "MANAGER"],
            ).exists()

            has_submitted_report = obj.technical_reports.filter(
                user=user,
                status="SUBMITTED",
            ).exists()

            return {
                "can_start": (
                    is_assigned
                    and obj.status == "TODO"
                ),

                "can_pause": (
                    is_assigned
                    and obj.status == "INPROGRESS"
                ),

                "can_send_to_review": (
                    is_assigned
                    and obj.status == "INPROGRESS"
                    and has_submitted_report
                ),

                "can_mark_done_directly": (
                    is_manager
                    and is_assigned
                    and obj.status in ["TODO", "INPROGRESS"]
                ),

                "can_reassign": is_manager,

                "can_change_status": is_assigned ,
            }
    def get_permissions(self, obj):
        request = self.context.get("request")
        user = request.user if request else None

        if not user or not user.is_authenticated:
            return {
                "can_view": False,
                "can_update": False,
                "can_delete": False,
                "can_assign": False,
                "can_submit_report": False,
                "can_create_task": False,
                "can_view_reports": False,
            }

        is_assigned = obj.assigned_to_id == user.id

        role = obj.project.projectrole_set.filter(
            user=user
        ).values_list("role", flat=True).first()

        is_manager = role in ["ADMIN", "MANAGER"]
        is_employee = role == "EMPLOYEE"
        is_viewer = role == "VIEWER"
        is_owner = obj.project.workspace.creator_id == user.id

        return {
            "can_view": (
                is_assigned
                or is_manager or is_owner or is_viewer
            ),

            "can_update": is_manager or is_owner,
            "can_update_status":is_assigned,
            "can_delete": is_manager or is_owner,
            "can_assign": is_manager or is_owner,
            "can_create_task": is_manager or is_owner,
            "can_submit_report": (is_employee and is_assigned and obj.status == "INPROGRESS"),
            "can_view_reports": ( is_manager or is_owner or is_assigned),
            "can_view_unassigned_tasks": (is_manager or is_owner),
            "can_view_archived_tasks": (is_manager or is_owner),

            "can_view_deleted_tasks": (is_manager or is_owner),
            "can_restore_tasks": (is_manager or is_owner),
            "can_assign_tasks": (is_manager or is_owner),
            "can_manage_dependencies": (is_manager or is_owner),


            "can_mark_done_directly":(is_manager
                and is_assigned
                and obj.status in [
                    "INPROGRESS",
                    "PAUSED",
                ]),
            "can_send_to_review": (
                is_employee
                and is_assigned
                and obj.status == "INPROGRESS"),

        }

    def get_state_label(self, obj):
        if obj.is_deleted:
            return "DELETED"

        if obj.status == "DONE":
            return "DONE"

        if obj.is_blocked:
            return "BLOCKED"

        if obj.status == "PAUSED":
            return "PAUSED"

        if obj.status == "REVIEW":
            return "IN_REVIEW"

        if obj.status == "INPROGRESS":
            return "IN_PROGRESS"

        if obj.status == "TODO" and obj.can_start:
            return "READY"

        return obj.status
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
        if obj.status == "DONE":
            return False

        if not obj.due_date:
            return False

        return timezone.now() > obj.due_date


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

##################################################
##################################################
##################################################
class TaskDependencySerializer(serializers.ModelSerializer):
    predecessor_title = serializers.CharField(
        source="predecessor.title",
        read_only=True,
    )
    successor_title = serializers.CharField(
        source="successor.title",
        read_only=True,
    )

    class Meta:
        model = TaskDependency
        fields = [
            "id",
            "predecessor",
            "predecessor_title",
            "successor",
            "successor_title",
            "dependency_type",
            "created_by",
            "created_at",
        ]

        read_only_fields = [
            "id",
            "created_by",
            "created_at",
            "predecessor_title",
            "successor_title",
        ]

class AddTaskDependencySerializer(serializers.Serializer):
    predecessor_id = serializers.PrimaryKeyRelatedField(
        source="predecessor",
        queryset=Task.objects.filter(is_deleted=False),
    )

    dependency_type = serializers.ChoiceField(
        choices=TaskDependency.DEPENDENCY_TYPES,
        default="BLOCKS",
        required=False,
    )

##################################################
##################################################
##################################################
##################################################
class TaskCreateUpdateSerializer(serializers.ModelSerializer):
    image_files = serializers.ListField(child=serializers.ImageField(), write_only=True, required=False)
    document_files = serializers.ListField(child=serializers.FileField(), write_only=True, required=False)
    due_date = serializers.DateTimeField(
        input_formats=["%d-%m-%Y", "%d/%m/%Y", "%Y-%m-%d", "%Y-%m-%dT%H:%M:%S%z", "iso-8601"]
    )
    dependency_ids = serializers.PrimaryKeyRelatedField(
        queryset=Task.objects.filter(
            is_deleted=False,
            is_archived=False,
        ),
        many=True,
        required=False,
        write_only=True,
    )

    class Meta:
        model = Task
        fields = [
            'id', 'project', 'title', 'description', 'priority', 'status','dependency_ids',
            'expected_duration', 'link', 'assigned_to', 'image_files',
            'document_files', 'due_date'
        ]
        read_only_fields = ['id']


    def validate(self, attrs):
        project = attrs.get("project")
        parent = attrs.get("parent")
        assigned_to = attrs.get("assigned_to")
        dependencies = attrs.get("dependency_ids", [])


        expected_duration = attrs.get('expected_duration')
        if expected_duration and expected_duration.total_seconds() <= 0:
                    raise serializers.ValidationError({"expected_duration": "it must be greater than 0"})

        if parent and parent.project_id != project.id:
            raise serializers.ValidationError({
                "parent": "The parent task must belong to the same project."
            })

        for dependency_task in dependencies:
            if dependency_task.project_id != project.id:
                raise serializers.ValidationError({
                    "dependency_ids": (
                        f"Task {dependency_task.id} does not belong "
                        "to the selected project."
                    )
                })

        if parent and parent in dependencies:
            raise serializers.ValidationError({
                "dependency_ids": (
                    "The parent task should not automatically be used "
                    "as a blocking dependency."
                )
            })

        if assigned_to:

            is_member = project.members.filter(
                pk=assigned_to.pk
            ).exists()

            if not is_member:
                raise serializers.ValidationError({
                    "assigned_to": (
                        "The selected employee is not a project member."
                    )
                })

        return attrs

    def create(self, validated_data):
        image_files = validated_data.pop('image_files', [])
        document_files = validated_data.pop('document_files', [])
        dependencies = validated_data.pop("dependency_ids", [])
        request = self.context.get('request')

        task = Task.objects.create(**validated_data)
        for dependency_task in dependencies:
            TaskDependency.objects.create(
                predecessor=dependency_task,
                successor=task,
                dependency_type="BLOCKS",
                created_by=request.user,
            )
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
        def validate(self, attrs):
            status_value = attrs.get("status")
            feedback_text = attrs.get("feedback_text")

            if status_value == "REJECTED" and not feedback_text:
                raise serializers.ValidationError({
                    "feedback_text": "Feedback is required when rejecting a report."
                })

            if status_value not in ["APPROVED", "REJECTED"]:
                raise serializers.ValidationError({
                    "status": "Status must be APPROVED or REJECTED."
                })

            return attrs



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
        if obj.user.is_deleted:
            return "Deleted User"
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



from rest_framework import serializers

from users.models import ActivityLog


class TaskHistorySerializer(
    serializers.ModelSerializer
):
    actor = serializers.SerializerMethodField()

    class Meta:
        model = ActivityLog
        fields = [
            "id",
            "action",
            "action_id",
            "actor",
            "changes",
            "created_at",
        ]

    def get_actor(self, obj):
        if not obj.user:
            return None

        return {
            "id": obj.user.id,
            "username": obj.user.username,
            "full_name": (
                obj.user.get_full_name()
                or obj.user.username
            ),
            "avatar": self._avatar_url(
                obj.user,
            ),
        }

    def _avatar_url(self, user):
        if not getattr(user, "avatar", None):
            return None

        request = self.context.get("request")
        url = user.avatar.url

        if request:
            return request.build_absolute_uri(url)

        return url
class WorkspaceProjectTasksSerializer(
    serializers.Serializer
):
    id = serializers.IntegerField(
        source="project.id"
    )
    name = serializers.CharField(
        source="project.name"
    )
    status = serializers.CharField(
        source="project.status"
    )
    status_display = serializers.CharField(
        source="project.get_status_display"
    )
    tasks_count = serializers.IntegerField()
    tasks = TaskSerializer(
        many=True,
        read_only=True,
    )


class UserWorkspaceTasksGroupedSerializer(
    serializers.Serializer
):
    workspace_id = serializers.IntegerField()
    total_tasks = serializers.IntegerField()
    projects = WorkspaceProjectTasksSerializer(
        many=True,
    )

class WorkspaceTeamMemberSerializer(
    serializers.Serializer
):
    id = serializers.IntegerField(
        source="member.id",
    )

    username = serializers.CharField(
        source="member.username",
    )

    first_name = serializers.CharField(
        source="member.first_name",
    )

    last_name = serializers.CharField(
        source="member.last_name",
    )

    avatar = serializers.SerializerMethodField()

    workspace_role = serializers.CharField()
    tasks_count = serializers.IntegerField()

    projects = WorkspaceProjectTasksSerializer(
        many=True,
    )

    def get_avatar(self, obj):
        member = obj["member"]

        if not member.avatar:
            return None

        request = self.context.get("request")
        url = member.avatar.url

        if request:
            return request.build_absolute_uri(url)

        return url


class WorkspaceTeamTasksGroupedSerializer(
    serializers.Serializer
):
    workspace_id = serializers.IntegerField()
    total_members = serializers.IntegerField()
    total_tasks = serializers.IntegerField()

    members = WorkspaceTeamMemberSerializer(
        many=True,
    )



class ProjectTeamMemberTasksSerializer(
    serializers.Serializer
):
    id = serializers.IntegerField(
        source="member.id",
    )

    username = serializers.CharField(
        source="member.username",
    )

    first_name = serializers.CharField(
        source="member.first_name",
    )

    last_name = serializers.CharField(
        source="member.last_name",
    )

    avatar = serializers.SerializerMethodField()

    project_role = serializers.CharField()

    tasks_count = serializers.IntegerField()

    tasks = TaskSerializer(
        many=True,
        read_only=True,
    )

    def get_avatar(self, obj):
        member = obj["member"]

        if not member.avatar:
            return None

        request = self.context.get("request")
        url = member.avatar.url

        if request:
            return request.build_absolute_uri(url)

        return url


class ProjectTeamTasksGroupedSerializer(
    serializers.Serializer
):
    project_id = serializers.IntegerField()

    project_name = serializers.CharField()

    total_members = serializers.IntegerField()

    total_tasks = serializers.IntegerField()

    members = ProjectTeamMemberTasksSerializer(
        many=True,
    )