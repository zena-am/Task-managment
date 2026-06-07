from drf_spectacular.utils import extend_schema
from django.shortcuts import get_object_or_404
from rest_framework import viewsets, permissions, status
from rest_framework.response import Response

from users.services.WorkspaceService import WorkspaceServices
from ..models import User, WorkSpace, WorkSpaceMember, Invitation
from ..serializers import WorkSpaceSerializer,WorkSpaceCreateSerializer
from ..permissions import  IsProfileComplete, IsWorkspaceOwnerOrReadOnly
from users.views.invitations import InvitationViewSet
from django.db.models import Case, When, Value, BooleanField
from drf_spectacular.utils import extend_schema, extend_schema_view
from rest_framework.decorators import APIView, action

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

                return Response(result, status=status.HTTP_200_OK)

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

                return Response(result, status=status.HTTP_200_OK)



        @extend_schema(summary="نقل ملكية الفضاء")
        @action(detail=True, methods=['post'], url_path='transfer-ownership')
        def transfer_ownership(self, request, pk=None):
                workspace = self.get_object()
                new_owner_id = request.data.get('new_owner_id')

                try:
                        new_owner = User.objects.get(id=new_owner_id)
                        WorkspaceServices.transfer_ownership(workspace, new_owner, request.user)
                        return Response({"message": "تم نقل الملكية بنجاح"})
                except User.DoesNotExist:
                        return Response({"error": "المستخدم غير موجود"}, status=404)
                except Exception as e:
                        return Response({"error": str(e)}, status=400)





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