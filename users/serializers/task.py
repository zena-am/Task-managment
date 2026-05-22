from datetime import timedelta
from django.utils import timezone
from rest_framework import serializers
from users.serializers.user import UserSerializer
from ..models import Task,TaskImage,TaskFile, TechnicalReportForm


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

    assigned_to_detail = UserSerializer(source='assigned_to', read_only=True)
    supervisor_detail = UserSerializer(source='supervisor', read_only=True)

    time_expected_hours = serializers.SerializerMethodField()
    actual_duration_hours = serializers.SerializerMethodField()
    is_overdue=serializers.SerializerMethodField()
    images = TaskImageSerializer(many=True, read_only=True)
    files = TaskFileSerializer(many=True, read_only=True)


    class Meta:
        model = Task
        fields = [
            'id', 'title', 'project', 'status', 'status_display', 'priority', 'priority_display',
            'expected_duration', 'time_expected_hours', 'actual_duration', 'actual_duration_hours',
            'start_time', 'end_time', 'link',
            'assigned_to', 'assigned_to_detail', 'supervisor', 'supervisor_detail', 'is_overdue','images','files'
        ]

        read_only_fields = ['start_time', 'end_time']

    def get_expected_duration_hours(self, obj):
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
            deadline = obj.start_time + obj.time_expected
            return timezone.now() > deadline

        if not obj.start_time and obj.created_at and obj.expected_duration:
            deadline_from_creation = obj.created_at + obj.expected_duration
            return timezone.now() > deadline_from_creation

        return False


###########################################################################################################



class TaskCreateUpdateSerializer(serializers.ModelSerializer):
    image_files = serializers.ListField(child=serializers.ImageField(),write_only=True, required=False )

    document_files = serializers.ListField(child=serializers.FileField(),write_only=True, required=False )

    class Meta:
        model = Task
        fields = [
            'id', 'project', 'title', 'description', 'priority', 'status',
            'expected_duration', 'link',
            'assigned_to', 'supervisor','image_files','document_files',
        ]
        read_only_fields = ['id']

    def validate(self, attrs):
        expected_duration = attrs.get('expected_duration')
        if expected_duration and expected_duration.total_seconds() <= 0:
            raise serializers.ValidationError({"time_expected": "it must be greater than 0"})
        return attrs


    def create(self, validated_data):
        image_files = validated_data.pop('image_files', [])
        document_files = validated_data.pop('document_files', [])
        request = self.context.get('request')

        task = Task.objects.create(
            creator=request.user,
            **validated_data
        )

        for image in image_files:
            TaskImage.objects.create(
                task=task,
                user=request.user,
                image=image
            )

        for file in document_files:
            TaskFile.objects.create(
                task=task,
                user=request.user,
                file=file
            )

        return task

    def update(self, instance, validated_data):
        image_files = validated_data.pop('image_files', [])
        document_files = validated_data.pop('document_files', [])
        request = self.context.get('request')

        for attr, value in validated_data.items():
            setattr(instance, attr, value)

        instance.save()

        for image in image_files:
            TaskImage.objects.create(
                task=instance,
                user=request.user,
                image=image
            )

        for file in document_files:
            TaskFile.objects.create(
                task=instance,
                user=request.user,
                file=file
            )

        return instance


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
    class Meta:
        model = TechnicalReportForm
        fields = ['id', 'status', 'description', 'manager_feedbacks']