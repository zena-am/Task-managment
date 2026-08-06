from rest_framework import serializers

from users.views.tasks import User
from ..models import LeaveTaskAction, ProjectRole, Task, TechnicalReportForm, RequestForm, BugReportForm

class TechnicalReportSerializer(serializers.ModelSerializer):
    user = serializers.HiddenField(default=serializers.CurrentUserDefault())

    class Meta:
        model = TechnicalReportForm
        fields = [ 'id','task', 'description', 'image', 'file', 'duration_time', 'url', 'quality', 'user', 'status', 'manager_feedback','manager_feedbacks',]
        read_only_fields = ['id','status', 'manager_feedback', 'manager_feedbacks','s']

class RequestFormSerializer(serializers.ModelSerializer):
    user = serializers.HiddenField(default=serializers.CurrentUserDefault())

    class Meta:
        model = RequestForm
        fields = ['leave_start','leave_end' ,'id','request_type', 'priority', 'project', 'title', 'file', 'image', 'time', 'reason', 'user','status', 'manager_feedback']
        read_only_fields = ['id','status', 'manager_feedback']

    def validate(self, attrs):
        instance = getattr(self, "instance", None)

        request_type = attrs.get(
            "request_type",
            getattr(instance, "request_type", None),
        )

        leave_start = attrs.get(
            "leave_start",
            getattr(instance, "leave_start", None),
        )

        leave_end = attrs.get(
            "leave_end",
            getattr(instance, "leave_end", None),
        )

        if request_type == "LEAVE":
            if not leave_start:
                raise serializers.ValidationError({
                    "leave_start": (
                        "Leave start is required for leave requests."
                    )
                })

            if not leave_end:
                raise serializers.ValidationError({
                    "leave_end": (
                        "Leave end is required for leave requests."
                    )
                })

            if leave_end <= leave_start:
                raise serializers.ValidationError({
                    "leave_end": (
                        "Leave end must be after leave start."
                    )
                })

        return attrs

############################################
############################################
class LeaveTaskActionSerializer(serializers.ModelSerializer):
    task_title = serializers.CharField(
        source="task.title",
        read_only=True,
    )

    task_status = serializers.CharField(
        source="task.status",
        read_only=True,
    )

    current_assignee = serializers.SerializerMethodField()

    new_assignee_name = serializers.SerializerMethodField()

    action_display = serializers.CharField(
        source="get_action_display",
        read_only=True,
    )
    resolved_by_name = serializers.SerializerMethodField()

    class Meta:
        model = LeaveTaskAction
        fields = [
            'resolved_by_name',
            "id",
            "request",
            "task",
            "task_title",
            "task_status",
            "current_assignee",
            "impact",
            "requires_action",
            "action",
            "action_display",
            "new_assignee",
            "new_assignee_name",
            "new_due_date",
            "is_resolved",
            "created_at",
            "updated_at",
            "previous_task_status",
            "previous_assignee",
            "previous_due_date",

"resolved_by",
"resolved_at",
        ]

        read_only_fields = [
            "id",
            "request",
            "task",
            "task_title",
            "task_status",
            "current_assignee",
            "impact",
            "requires_action",
            "is_resolved",
            "created_at",
            'resolved_by_name',
            "updated_at",
        ]

    def get_resolved_by_name(self, obj):
        if not obj.resolved_by:
            return None

        return (
            obj.resolved_by.get_full_name()
            or obj.resolved_by.username
        )
    def get_current_assignee(self, obj):
        user = obj.task.assigned_to

        if not user:
            return None

        return {
            "id": user.id,
            "name": user.get_full_name() or user.username,
        }

    def get_new_assignee_name(self, obj):
        if not obj.new_assignee:
            return None

        return (
            obj.new_assignee.get_full_name()
            or obj.new_assignee.username
        )




class ResolveLeaveTaskActionSerializer(serializers.Serializer):
    action = serializers.ChoiceField(
        choices=LeaveTaskAction.ACTION_CHOICES,
    )

    new_assignee = serializers.PrimaryKeyRelatedField(
        queryset=User.objects.all(),
        required=False,
        allow_null=True,
    )

    new_due_date = serializers.DateTimeField(
        required=False,
        allow_null=True,
    )


    def validate(self, attrs):
        leave_action = self.context.get("leave_action")

        action = attrs.get("action")
        new_assignee = attrs.get("new_assignee")
        new_due_date = attrs.get("new_due_date")

        if action == "TRANSFER_TASK":
            if not new_assignee:
                raise serializers.ValidationError({
                    "new_assignee": (
                        "New assignee is required when "
                        "transferring the task."
                    )
                })

            if leave_action:
                if new_assignee == leave_action.task.assigned_to:
                    raise serializers.ValidationError({
                        "new_assignee": (
                            "The new assignee must be different "
                            "from the current assignee."
                        )
                    })

            attrs["new_due_date"] = None

        elif action == "EXTEND_DUE_DATE":
            if not new_due_date:
                raise serializers.ValidationError({
                    "new_due_date": (
                        "New due date is required when "
                        "extending the task."
                    )
                })



            attrs["new_assignee"] = None

        elif action in ["PAUSE_TASK", "NO_ACTION"]:
            attrs["new_assignee"] = None
            attrs["new_due_date"] = None

        return attrs



class BugLinkedTaskSerializer(serializers.ModelSerializer):
    assigned_to_name = serializers.SerializerMethodField()
    status_display = serializers.CharField(
        source="get_status_display",
        read_only=True,
    )

    class Meta:
        model = Task
        fields = [
            "id",
            "title",
            "status",
            "status_display",
            "priority",
            "due_date",
            "assigned_to",
            "assigned_to_name",
        ]

    def get_assigned_to_name(self, obj):
        if not obj.assigned_to:
            return None

        return (
            obj.assigned_to.get_full_name()
            or obj.assigned_to.username
        )

class BugReportSerializer(serializers.ModelSerializer):
    linked_tasks = serializers.SerializerMethodField()
    reporter_name = serializers.CharField(
        source="user.username",
        read_only=True,
    )

    project_name = serializers.CharField(
        source="project.name",
        read_only=True,
    )

    task_title = serializers.CharField(
        source="task.title",
        read_only=True,
        default=None,
    )

    permissions = serializers.SerializerMethodField()

    class Meta:
        model = BugReportForm
        fields = [
            'linked_tasks',
            "id",
            "project",
            "project_name",
            "user",
            "reporter_name",
            "task",
            "task_title",
            "status",
            "dangerous_level",
            "title",
            "description",
            "url",
            "file",
            "image",
            "result",
            "permissions",
            "created_at",
            "updated_at",
        ]

        read_only_fields = [
            "user",
            "task",
            "status",
            "result",
            "created_at",
            "updated_at",
        ]

    def get_permissions(self, obj):
        request = self.context.get("request")
        user = request.user if request else None

        if not user or not user.is_authenticated:
            return {}

        is_reporter = obj.user_id == user.id

        is_manager = (
        ProjectRole.objects.filter(
            project=obj.project,
            user=user,
            role__in=["ADMIN", "MANAGER"],
        ).exists()
        or obj.project.workspace.creator_id == user.id
)
        has_active_task = obj.task_links.filter(
            task__status__in=[
                "TODO",
                "INPROGRESS",
                "REVIEW",
                "PAUSED",
            ],
            task__is_deleted=False,
            task__is_archived=False,
        ).exists()
        return {
            "can_edit": (
                is_reporter
                and obj.status == "OPEN"
                and obj.task_id is None
            ),
            "can_delete": (
                is_reporter
                and obj.status == "OPEN"
                and obj.task_id is None
            ),
            "can_convert_to_task": (
                is_manager
                and obj.status == "OPEN"
                and not has_active_task
            ),
            "can_verify": (
                is_reporter
                and obj.task_id is not None
                and obj.task.status == "DONE"
                and obj.status in ["OPEN", "FIXED"]
            ),
            "can_close": (
                is_manager
                and obj.status in ["OPEN", "FIXED", "VERIFIED"]
            ),
            "can_view_task": obj.task_id is not None,
        }
    def get_linked_tasks(self, obj):
        tasks = Task.objects.filter(
            bug_link__bug=obj,
        ).select_related(
            "assigned_to",
        ).order_by(
            "-created_at",
        )

        return BugLinkedTaskSerializer(
            tasks,
            many=True,
            context=self.context,
        ).data

class ManagerRequestReviewSerializer(serializers.ModelSerializer):
    status = serializers.ChoiceField(
        choices=["APPROVED", "REJECTED"]
    )

    manager_feedback = serializers.CharField(
        required=False,
        allow_blank=True,
        allow_null=True
    )

    class Meta:
        model = RequestForm
        fields = [
            "status",
            "manager_feedback",
        ]
class BugToTaskSerializer(serializers.Serializer):
    assigned_to = serializers.PrimaryKeyRelatedField(
        queryset=User.objects.filter(
            is_active=True,
            is_deleted=False,
        ),
        required=False,
        allow_null=True,
    )

    expected_duration = serializers.DurationField()

    due_date = serializers.DateTimeField()

    priority = serializers.ChoiceField(
        choices=Task.PRIORITY_CHOICES,
        required=False,
    )


    def validate(self, attrs):
        bug = self.context["bug"]
        assigned_to = attrs.get("assigned_to")

        if assigned_to:
            is_member = ProjectRole.objects.filter(
                project=bug.project,
                user=assigned_to,
            ).exists()

            if not is_member:
                raise serializers.ValidationError({
                    "assigned_to": (
                        "The selected user is not a member "
                        "of this project."
                    )
                })

        return attrs
