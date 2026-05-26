from rest_framework import serializers


class GoogleAuthSerializer(serializers.Serializer):
    firebase_token = serializers.CharField(help_text="Firebase ID token coming from Flutter")


class GoogleAuthResponseSerializer(serializers.Serializer):
    access = serializers.CharField()
    refresh = serializers.CharField()
    username = serializers.CharField()
    email = serializers.EmailField()