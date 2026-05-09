from rest_framework.decorators import api_view, permission_classes
from rest_framework.response import Response
from django.contrib.auth import get_user_model
from rest_framework.response import Response
from rest_framework import status
from .models import Profile
from rest_framework.permissions import IsAuthenticated
from django.shortcuts import render
from rest_framework.decorators import  permission_classes
from rest_framework.response import Response
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework import status
from .models import Profile
from .serializers import ProfileSerializer

@api_view(['GET', 'PUT'])
@permission_classes([IsAuthenticated])
def profile(request):
    try:

        user_profile = request.user.profile
    except Profile.DoesNotExist:
        return Response({"error": "Profile not found"}, status=status.HTTP_404_NOT_FOUND)

    if request.method == 'GET':
        serializer = ProfileSerializer(user_profile, context={'request': request})
        return Response(serializer.data)

    if request.method == 'PUT':

        serializer = ProfileSerializer(user_profile, data=request.data, partial=True)
        
        if serializer.is_valid():
            serializer.save()
            return Response(serializer.data, status=status.HTTP_200_OK)
        
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)



User = get_user_model()
############################################################################################google signUp

@api_view(['PATCH'])
@permission_classes([IsAuthenticated])
def update_profile(request):
    profile = request.user.profile


    serializer = ProfileSerializer(profile, data=request.data, partial=True)

    if serializer.is_valid():


        serializer.save()

        return Response({
            "message": "updated ",
            "data": serializer.data
        })
    return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
###########################################################
