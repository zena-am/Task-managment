"""




class TaskSerializer(serializers.ModelSerializer):
    priority_display = serializers.CharField(source='get_priority_display', read_only=True)
    status_display = serializers.CharField(source='get_status_display', read_only=True)

    assigned_to_detail = UserSerializer(source='assigned_to', read_only=True)
    supervisor_detail = UserSerializer(source='supervisor', read_only=True)

    time_expected_hours = serializers.SerializerMethodField()
    actual_duration_hours = serializers.SerializerMethodField()
    is_overdue=serializers.SerializerMethodField()

    class Meta:
        model = Task
        fields = [
            'id', 'title', 'project', 'status', 'status_display', 'priority', 'priority_display',
            'time_expected', 'time_expected_hours', 'actual_duration', 'actual_duration_hours',
            'strat_time', 'end_time', 'image', 'file', 'link', 'extra_data',
            'assigned_to', 'assigned_to_detail', 'supervisor', 'supervisor_detail','is_overdue'
        ]

        read_only_fields = ['strat_time', 'end_time']

    def get_time_expected_hours(self, obj):
        if obj.time_expected:
            return obj.time_expected.total_seconds() / 3600
        return 0

    def get_actual_duration_hours(self, obj):
        if obj.actual_duration:
            return obj.actual_duration.total_seconds() / 3600
        return None


    def get_is_overdue(self, obj):
        if obj.status == 'DONE':
            return False

        if obj.start_time and obj.time_expected:
            deadline = obj.start_time + obj.time_expected
            return timezone.now() > deadline

        if not obj.start_time and obj.created_at and obj.time_expected:
            deadline_from_creation = obj.created_at + obj.time_expected
            return timezone.now() > deadline_from_creation

        return False
    def get_supervisor_details(self, obj):
        if obj.supervisor:
            return {
                "id": obj.supervisor.id,
                "username": obj.supervisor.username,
                "email": obj.supervisor.email
            }
        return None

    def get_assigned_to_details(self, obj):
        if obj.assigned_to:
            return {
                "id": obj.assigned_to.id,
                "username": obj.assigned_to.username,
                "position": obj.assigned_to.profile.position if hasattr(obj.assigned_to, 'profile') else None
            }
        return None

###########################################################################################################



class TaskCreateUpdateSerializer(serializers.ModelSerializer):
    class Meta:
        model = Task
        fields = [
            'id', 'project', 'title', 'description', 'priority', 'status',
            'time_expected', 'image', 'file', 'link',
            'assigned_to', 'supervisor'
        ]
        read_only_fields = ['id']

    def validate(self, attrs):
        time_expected = attrs.get('time_expected')
        if time_expected and time_expected.total_seconds() <= 0:
            raise serializers.ValidationError({"time_expected": "it must be greater than 0"})
        return attrs"""