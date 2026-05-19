from rest_framework import permissions
from django.db.models import Q
from .models import ProjectRole
from rest_framework.permissions import BasePermission, IsAuthenticated

class IsCreatorOrReadOnly(permissions.BasePermission):
    message = "you aren't the creator of this workspace"
    def has_object_permission(self, request, view, obj):
        if request.method in permissions.SAFE_METHODS:
            return True
        return obj.creator == request.user



class IsProjectManagerOrReadOnly(permissions.BasePermission):
    message = "you aren't the creator of this project"
    def has_object_permission(self, request, view, obj):
        if request.method in permissions.SAFE_METHODS:
            return True

        return ProjectRole.objects.filter(project=obj,user=request.user).filter(Q(role='MANAGER') | Q(role='ADMIN')).exists()

class IsProfileComplete(BasePermission):

    message = ""

    def has_permission(self, request, view):
        user = request.user
        if user.is_authenticated:
            return bool(user.avatar and user.position and user.bio)
        return False
