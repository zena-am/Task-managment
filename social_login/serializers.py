from rest_framework import serializers

class GoogleAuthSerializer(serializers.Serializer):
    firebase_token = serializers.CharField(help_text="التوكن المستلم من Firebase في تطبيق الفلاتر")

