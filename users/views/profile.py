from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework import status
from drf_spectacular.utils import extend_schema

from rest_framework import generics, status
from rest_framework.permissions import IsAuthenticated
from rest_framework.parsers import MultiPartParser, FormParser
from rest_framework.response import Response

from users.errors.messages.success import success_response
from users.serializers.user import UpdateProfileSerializer


class ProfileView(generics.RetrieveUpdateAPIView):
    permission_classes = [IsAuthenticated]
    serializer_class = UpdateProfileSerializer
    parser_classes = [MultiPartParser, FormParser]

    def get_object(self):
        return self.request.user

    def retrieve(self, request, *args, **kwargs):
        user = self.get_object()
        serializer = self.get_serializer(user)

        data = serializer.data
        data["username"] = user.username
        data["email"] = user.email
        data["is_profile_completed"] = bool(user.avatar and user.phone)

        return Response(
            success_response(
                message="Profile retrieved successfully",
                code="PROFILE_RETRIEVED",
                data=data,
            ),
            status=status.HTTP_200_OK,
        )

    def update(self, request, *args, **kwargs):
        partial = kwargs.pop("partial", False)
        user = self.get_object()

        serializer = self.get_serializer(
            user,
            data=request.data,
            partial=partial,
        )
        serializer.is_valid(raise_exception=True)
        serializer.save()

        data = serializer.data
        data["username"] = user.username
        data["email"] = user.email
        data["is_profile_completed"] = bool(user.avatar and user.phone)

        return Response(
            success_response(
                message="Profile updated successfully",
                code="PROFILE_UPDATED",
                data=data,
            ),
            status=status.HTTP_200_OK,
        )