from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework import status
from drf_spectacular.utils import extend_schema

"""
@extend_schema(
    tags=['البروفايل'],
    summary="جلب أو تحديث بيانات المستخدم الحالي",
    responses={200: ProfileSerializer}
)
@api_view(['GET', 'PUT', 'PATCH'])
@permission_classes([IsAuthenticated])
def profile(request):

    user_profile, created = Profile.objects.get_or_create(user=request.user)
    user_profile, created = Profile.objects.get_or_create(user=request.user)

    if request.method == 'GET':
        serializer = ProfileSerializer(user_profile)
        return Response(serializer.data)

    if request.method in ['PUT', 'PATCH']:
        serializer = ProfileSerializer(user_profile, data=request.data, partial=True)
        if serializer.is_valid():
            serializer.save()
            return Response({
                "message": "updated successfully",
                "data": serializer.data
            })
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
"""