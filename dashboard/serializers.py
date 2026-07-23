from rest_framework import serializers

from users.models import ActivityLog


class DashboardScopeSerializer(serializers.Serializer):
    workspace_id = serializers.IntegerField(allow_null=True)
    workspace_name = serializers.CharField(allow_null=True)


class TaskOverviewSerializer(serializers.Serializer):
    total = serializers.IntegerField()
    todo = serializers.IntegerField()
    in_progress = serializers.IntegerField()
    review = serializers.IntegerField()
    completed = serializers.IntegerField()
    overdue = serializers.IntegerField()
    due_soon = serializers.IntegerField()
    unassigned = serializers.IntegerField()


class StatusOverviewSerializer(serializers.Serializer):
    total = serializers.IntegerField()
    pending = serializers.IntegerField(required=False)
    draft = serializers.IntegerField(required=False)
    submitted = serializers.IntegerField(required=False)
    approved = serializers.IntegerField(required=False)
    rejected = serializers.IntegerField(required=False)
    open = serializers.IntegerField(required=False)
    fixed = serializers.IntegerField(required=False)
    verified = serializers.IntegerField(required=False)
    closed = serializers.IntegerField(required=False)


class DashboardOverviewSerializer(serializers.Serializer):
    scope = DashboardScopeSerializer()
    workspaces_count = serializers.IntegerField()
    projects_count = serializers.IntegerField()
    members_count = serializers.IntegerField()
    tasks = TaskOverviewSerializer()
    reports = StatusOverviewSerializer()
    requests = StatusOverviewSerializer()
    bugs = StatusOverviewSerializer()


class ActivityLogSerializer(serializers.ModelSerializer):
    user = serializers.SerializerMethodField()
    action_display = serializers.CharField(source="get_action_display", read_only=True)

    class Meta:
        model = ActivityLog
        fields = [
            "id",
            "user",
            "action",
            "action_display",
            "action_id",
            "changes",
            "created_at",
            "updated_at",
        ]

    def get_user(self, obj):
        return {
            "id": obj.user_id,
            "username": obj.user.username,
            "full_name": f"{obj.user.first_name} {obj.user.last_name}".strip()
            or obj.user.username,
            "email": obj.user.email,
        }


class PerformanceQuerySerializer(serializers.Serializer):
    workspace_id = serializers.IntegerField(required=False, min_value=1)
    project_id = serializers.IntegerField(required=False, min_value=1)
    employee_id = serializers.IntegerField(required=False, min_value=1)
    date_from = serializers.DateField(required=False)
    date_to = serializers.DateField(required=False)

    def validate(self, attrs):
        date_from = attrs.get("date_from")
        date_to = attrs.get("date_to")
        if date_from and date_to and date_from > date_to:
            raise serializers.ValidationError({"date_to": "Must be on or after date_from."})
        return attrs


class EmployeeIdentitySerializer(serializers.Serializer):
    id = serializers.IntegerField()
    username = serializers.CharField()
    full_name = serializers.CharField()
    email = serializers.EmailField()
    avatar = serializers.CharField(allow_null=True)


class WorkspacePerformanceReferenceSerializer(serializers.Serializer):
    id = serializers.IntegerField()
    name = serializers.CharField()
    projects = serializers.IntegerField()
    assigned_tasks = serializers.IntegerField()
    completed_tasks = serializers.IntegerField()
    completion_rate = serializers.FloatField()


class ProjectPerformanceReferenceSerializer(serializers.Serializer):
    id = serializers.IntegerField()
    name = serializers.CharField()
    workspace = serializers.DictField()
    role = serializers.CharField(allow_null=True)
    assigned_tasks = serializers.IntegerField()
    completed_tasks = serializers.IntegerField()
    overdue_tasks = serializers.IntegerField()
    completion_rate = serializers.FloatField()


class EmployeePerformanceSerializer(serializers.Serializer):
    employee = EmployeeIdentitySerializer()
    workspaces = WorkspacePerformanceReferenceSerializer(many=True)
    projects = ProjectPerformanceReferenceSerializer(many=True)
    tasks = serializers.DictField()
    reports = serializers.DictField()
    time = serializers.DictField()


class PerformanceListSerializer(serializers.Serializer):
    scope = serializers.DictField()
    employees_count = serializers.IntegerField()
    results = EmployeePerformanceSerializer(many=True)


class DashboardChartsSerializer(serializers.Serializer):
    scope = serializers.DictField()
    tasks_by_status = serializers.ListField(child=serializers.DictField())
    tasks_by_priority = serializers.ListField(child=serializers.DictField())
    reports_by_status = serializers.ListField(child=serializers.DictField())
    tasks_timeline_30_days = serializers.ListField(child=serializers.DictField())


class BulkTaskActionSerializer(serializers.Serializer):
    ACTION_CHOICES = (
        ("assign", "Assign"),
        ("reassign", "Reassign"),
        ("change_status", "Change status"),
        ("change_priority", "Change priority"),
        ("archive", "Archive"),
        ("restore", "Restore"),
        ("delete", "Soft delete"),
    )
    task_ids = serializers.ListField(child=serializers.IntegerField(min_value=1), allow_empty=False)
    action = serializers.ChoiceField(choices=ACTION_CHOICES)
    employee_id = serializers.IntegerField(required=False, min_value=1)
    status = serializers.ChoiceField(choices=("TODO", "INPROGRESS", "REVIEW", "DONE"), required=False)
    priority = serializers.ChoiceField(choices=("L", "M", "H"), required=False)

    def validate(self, attrs):
        action = attrs["action"]
        if action in ("assign", "reassign") and not attrs.get("employee_id"):
            raise serializers.ValidationError({"employee_id": "This field is required for assignment actions."})
        if action == "change_status" and not attrs.get("status"):
            raise serializers.ValidationError({"status": "This field is required."})
        if action == "change_priority" and not attrs.get("priority"):
            raise serializers.ValidationError({"priority": "This field is required."})
        attrs["task_ids"] = list(dict.fromkeys(attrs["task_ids"]))
        return attrs


class ExportQuerySerializer(PerformanceQuerySerializer):
    FORMAT_CHOICES = (("csv", "CSV"), ("xlsx", "Excel"), ("pdf", "PDF"))
    format = serializers.ChoiceField(choices=FORMAT_CHOICES, default="csv")
    resource = serializers.ChoiceField(choices=(("tasks", "Tasks"), ("reports", "Reports")), default="tasks")
    include_archived = serializers.BooleanField(default=False)


class ArchiveActionSerializer(serializers.Serializer):
    archive = serializers.BooleanField()
