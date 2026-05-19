from rest_framework import permissions
from rest_framework.decorators import api_view, permission_classes
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from rest_framework import status,viewsets
from django.shortcuts import render
from django.db.models import Q
from django.contrib.auth import get_user_model
from .models import Profile,WorkSpace,Project,WorkSpaceMember,ProjectRole,Invitation
from .serializers import ProfileSerializer,WorkSpaceSerializer,ProjectSerializer,UserSerializer,InvitationSerializer
from .permissions import IsCreatorOrReadOnly, IsProjectManagerOrReadOnly
from drf_spectacular.utils import extend_schema
from rest_framework.decorators import action
from drf_spectacular.utils import extend_schema, OpenApiExample
from drf_spectacular.utils import extend_schema, OpenApiExample, OpenApiResponse
from django.db import transaction
from .utils import notify_existing_user, notify_new_user
from rest_framework import viewsets, mixins

