from rest_framework import serializers
from ..models import ProjectRole, TechnicalReportForm, RequestForm, BugReportForm

class TechnicalReportSerializer(serializers.ModelSerializer):
    user = serializers.HiddenField(default=serializers.CurrentUserDefault())

    class Meta:
        model = TechnicalReportForm
        fields = [ 'id','task', 'description', 'image', 'file', 'duration_time', 'url', 'quality', 'user', 'status', 'manager_feedback','manager_feedbacks',]
        read_only_fields = ['id','status', 'manager_feedback', 'manager_feedbacks']

class RequestFormSerializer(serializers.ModelSerializer):
    user = serializers.HiddenField(default=serializers.CurrentUserDefault())

    class Meta:
        model = RequestForm
        fields = [ 'id','request_type', 'priority', 'project', 'title', 'file', 'image', 'time', 'reason', 'user','status', 'manager_feedback']
        read_only_fields = ['id','status', 'manager_feedback']


class BugReportSerializer(serializers.ModelSerializer):
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

        is_manager = ProjectRole.objects.filter(
            project=obj.project,
            user=user,
            role__in=["ADMIN", "MANAGER"],
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
                and obj.task_id is None
            ),
            "can_verify": (
                is_reporter
                and obj.task_id is not None
                and obj.task.status == "DONE"
                and obj.status in ["OPEN", "FIXED"]
            ),
            "can_close": (
                is_manager
                and obj.status == "VERIFIED"
            ),
            "can_view_task": obj.task_id is not None,
        }
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