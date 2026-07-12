from rest_framework import generics, status
from rest_framework.parsers import FormParser, MultiPartParser
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from users.errors.messages.success import success_response
from users.serializers.user import UpdateProfileSerializer
from users.services.user_service import UserService


class ProfileView(generics.RetrieveUpdateDestroyAPIView):
    permission_classes = [IsAuthenticated]
    serializer_class = UpdateProfileSerializer
    parser_classes = [MultiPartParser, FormParser]

    def get_object(self):
        return self.request.user

    def _serialized_profile(self, user):
        data = dict(self.get_serializer(user).data)
        data.update({
            "username": user.username,
            "email": user.email,
            "is_profile_completed": bool(user.avatar and user.phone),
        })
        return data

    def retrieve(self, request, *args, **kwargs):
        user = self.get_object()
        return Response(
            success_response(
                message="Profile retrieved successfully",
                code="PROFILE_RETRIEVED",
                data=self._serialized_profile(user),
            ),
            status=status.HTTP_200_OK,
        )

    def update(self, request, *args, **kwargs):
        partial = kwargs.pop("partial", False)
        user = self.get_object()
        serializer = self.get_serializer(user, data=request.data, partial=partial)
        serializer.is_valid(raise_exception=True)
        serializer.save()
        return Response(
            success_response(
                message="Profile updated successfully",
                code="PROFILE_UPDATED",
                data=self._serialized_profile(user),
            ),
            status=status.HTTP_200_OK,
        )

    def destroy(self, request, *args, **kwargs):
        result = UserService.soft_delete_account(request.user)
        return Response(
            success_response(
                message="Account deleted successfully",
                code="ACCOUNT_SOFT_DELETED",
                data=result,
            ),
            status=status.HTTP_200_OK,
        )
