from drf_spectacular.utils import extend_schema
from django.shortcuts import get_object_or_404
from rest_framework import viewsets, permissions, status
from rest_framework.response import Response

from users.errors.exceptions import BaseAppException, OnlyOneWorkspaceAdminError, PermissionDeniedError
from users.errors.messages.success import success_response
from users.services.WorkspaceService import WorkspaceServices
from ..models import User, WorkSpace, WorkSpaceMember, Invitation
from ..serializers import WorkSpaceSerializer,WorkSpaceCreateSerializer
from ..permissions import  IsProfileComplete, IsWorkspaceOwnerOrReadOnly
from users.views.invitations import InvitationViewSet
from django.db.models import Case, When, Value, BooleanField
from drf_spectacular.utils import extend_schema, extend_schema_view
from rest_framework.decorators import APIView, action
from django.db import transaction
from django.shortcuts import get_object_or_404


@extend_schema_view(
        tags=['الفضاءات'],
        list=extend_schema(tags=['فضاءات العمل'], summary="عرض فضاءات العمل الخاصة بالمستخدم مرتبة حسب التثبيت"),
        create=extend_schema(tags=['فضاءات العمل'], summary="إنشاء فضاء عمل جديد"),
        retrieve=extend_schema(tags=['فضاءات العمل'], summary="جلب تفاصيل فضاء عمل محدد"),
        update=extend_schema(tags=['فضاءات العمل'], summary="(للمالك)تحديث  كامل لفضاء العمل", description="هذا الاخيار يجب ان يظهر للمدير فقط"),
        destroy=extend_schema(tags=['فضاءات العمل'], summary="(للمدير)حذف فضاء العمل", description="هذا الاخيار يجب ان يظهر للمدير فقط")
)
class WorkspaceViewSet(viewsets.ModelViewSet):
        permission_classes = [permissions.IsAuthenticated, IsWorkspaceOwnerOrReadOnly]
        def get_serializer_class(self):

                if self.action in ['create', 'update', 'partial_update']:
                        return WorkSpaceCreateSerializer

                return WorkSpaceSerializer

        def get_queryset(self):
                user = self.request.user
                return WorkspaceServices.get_user_workspaces(user)

        def perform_update(self, serializer):
                WorkspaceServices.update_workspace(
                serializer=serializer,
                user=self.request.user,
                data=self.request.data)


        def perform_create(self, serializer):
                WorkspaceServices.create_workspace(
        serializer=serializer,
        user=self.request.user,
        data=self.request.data)

        @extend_schema(tags=['الفضاءات'], summary="نقل ملكية")
        @action(detail=True, methods=['post'], url_path='transfer')
        def transfer_owner(self, request, pk=None):
                new_owner_id = request.data.get("new_owner_id")

                if not new_owner_id:
                        raise BaseAppException(
                        detail="new_owner_id is required",
                        code="NEW_OWNER_REQUIRED",
                        status_code=400
                        )

                try:
                        new_owner_id = int(new_owner_id)
                except ValueError:
                        raise BaseAppException(
                        detail="new_owner_id must be a valid integer",
                        code="INVALID_NEW_OWNER_ID",
                        status_code=400
                        )

                workspace = get_object_or_404(WorkSpace, id=pk)
                new_owner = get_object_or_404(User, id=new_owner_id)

                if workspace.creator_id == new_owner_id:
                        raise BaseAppException(
                        detail="You are already the owner",
                        code="ALREADY_OWNER",
                        status_code=400
                        )

                if workspace.creator != request.user:
                        raise PermissionDeniedError()

                is_member = WorkSpaceMember.objects.filter(
                        workspace=workspace,
                        user=new_owner
                ).exists()

                if not is_member:
                        raise BaseAppException(
                        detail="User is not a member of this workspace",
                        code="USER_NOT_IN_WORKSPACE",
                        status_code=400
                        )

                WorkspaceServices.transfer_ownership(workspace, new_owner)

                return Response(success_response(
        message="Ownership transferred successfully",
        code="WORKSPACE_OWNERSHIP_TRANSFERRED",
        data=None
        ))



class TogglePinWorkspaceAPIView(APIView):
        permission_classes = [permissions.IsAuthenticated]
        @extend_schema(
        tags=['فضاءات العمل'],
        summary="(للموظف) تثبيت أو إلغاء تثبيت فضاء العمل",
        description="تسمح للموظف العادي بتثبيت الفضاء في أعلى قائمته الشخصية أو إلغاء تثبيته")
        def post(self, request, workspace_id):
                workspace = get_object_or_404(
                WorkSpace,
                id=workspace_id,
                members=request.user
                )

                result = WorkspaceServices.toggle_pin(
                user=request.user,
                workspace=workspace
                )

                return Response(success_response(
                        message="Workspace pin updated successfully",
                        code="WORKSPACE_PIN_UPDATED",
                        data=result))


class LeaveWorkspaceAPIView(APIView):
        permission_classes = [permissions.IsAuthenticated]
        @extend_schema(
                tags=['فضاءات العمل'],
                summary="(للموظف) مغادرة فضاء العمل",
                description="تسمح للموظف العادي بحذف نفسه ومغادرة فضاء العمل إذا لم يعد من الفريق، ولا يسمح للمالك بمغادرة فضائه بهذه الطريقة"
        )
        def delete(self, request, workspace_id):
                workspace = get_object_or_404(
                WorkSpace,
                id=workspace_id,
                members=request.user
                )

                result = WorkspaceServices.leave_workspace(
                user=request.user,
                workspace=workspace
                )

                return Response(success_response(
                message="Left workspace successfully",
                code="WORKSPACE_LEFT",
                data=result
                ))






"""
        def handle_invitations(self, workspace):
                from django.contrib.auth import get_user_model
                User = get_user_model()
                member_emails = self.request.data.get('member_emails', [])
                if isinstance(member_emails, str):member_emails = [member_emails]

                role = self.request.data.get('role', 'DEV')
                project_id = self.request.data.get('project_id')

                sender_name = self.request.user.get_full_name() or self.request.user.username
                workspace_name = workspace.name


                for email in member_emails:
                        existing_invitation = Invitation.objects.filter(receiver_email=email,workspace=workspace,project_id=project_id).first()

                        role = self.request.data.get('role', 'DEV')
                        if existing_invitation.status == 'ACCEPTED':
                                continue

                        if existing_invitation:
                                existing_invitation.status = 'PENDING'
                                existing_invitation.sender = self.request.user
                                existing_invitation.role = role
                                existing_invitation.save()
                                notify_existing_user(email, sender_name, workspace_name)
                                continue

                        receiver = User.objects.filter(email=email).first()


                        if receiver:
                                invitation = Invitation.objects.create(
                                sender=self.request.user,
                                receiver=receiver,
                                receiver_email=email,
                                project_id=project_id,
                                workspace=workspace,
                                role=role,
                                status='PENDING')
                                notify_existing_user(email, sender_name, workspace_name)


                        else:

                                invitation = Invitation.objects.create(
                                sender=self.request.user,
                                receiver_email=email,
                                project_id=project_id,
                                workspace=workspace,
                                role=role,
                                status='PENDING')
                                notify_new_user(email, sender_name, workspace_name)



"""