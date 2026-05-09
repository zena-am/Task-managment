from rest_framework import serializers
from users.models import User, Profile,Task,WorkSpace,WorkSpaceMember
from rest_framework_simplejwt.serializers import TokenObtainPairSerializer


class UserRegisterSerializer(serializers.ModelSerializer):
    password = serializers.CharField(write_only=True)

    class Meta:
        model = User
        fields = ['username', 'email', 'password']

    def create(self, validated_data):
        user = User.objects.create_user(
            username=validated_data['username'],
            email=validated_data['email'],
            password=validated_data['password']
        )
        Profile.objects.create(user=user)
        return user
##########################################################################################
class ProfileSerializer(serializers.ModelSerializer):
    class Meta:
        model = Profile
        fields = ['user', 'avatar', 'phone', 'position','bio'] # أضفنا user هنا
        read_only_fields = ['user','slug']
    

class MyTokenObtainPairSerializer(TokenObtainPairSerializer):
        username_field = 'email'
#########################################################################################
class WorkSpaceSerializer(serializers.ModelSerializer):
        members_details=serializers.SerializerMethodField()
        class Meta:
            model=WorkSpace
            fields=['members','name','to_date','date','discription','icon_name','members_details']

        def get_members_details(self,obj):
                workspace_members = WorkSpaceMember.objects.filter(workspace=obj)
                return [
                    {
            "username": member.user.username,
            "email": member.user.email,
            "position": member.position,
            "date_joined": member.date_joined
            }
            for member in workspace_members
            ]

class WorkSpaceListSerializer(serializers.ModelSerializer):
        class Meta:
            model=WorkSpace
            fields=['name','icon_name','members_details','date']

class TopbarListSerializer(serializers.ModelSerializer):
        class Meta:
                model=User
                fields=['']


class TaskReadSerializer(serializers.ModelSerializer):

        supervisor_details = serializers.SerializerMethodField()
        assigned_to_details = serializers.SerializerMethodField()

        class Meta:
            model = Task
            fields = [
            'id', 'title', 'status', 'priority',
            'time_expected', 'actual_duration',
            'supervisor_details', 'assigned_to_details',
            'strat_time', 'end_time' ]

        def get_supervisor_details(self, obj):
            return {
            "id": obj.supervisor.id,
            "username": obj.supervisor.username,
            "email": obj.supervisor.email
        }

        def get_assigned_to_details(self, obj):
            if obj.assigned_to:
                return {
                "id": obj.assigned_to.id,
                "username": obj.assigned_to.username,
                "position": obj.assigned_to.profile.position
            }
            return None