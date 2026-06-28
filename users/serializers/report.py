from rest_framework import serializers
from ..models import TechnicalReportForm, RequestForm, BugReportForm

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
    user = serializers.HiddenField(default=serializers.CurrentUserDefault())

    class Meta:
        model = BugReportForm
        fields = [ 'id','project', 'dangerous_level', 'title', 'description', 'url', 'file', 'image', 'user','status', 'result', 'assigned_to']
        read_only_fields = ['status', 'result', 'assigned_to']


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