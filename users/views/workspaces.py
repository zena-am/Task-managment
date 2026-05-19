from rest_framework import viewsets, permissions
from django.contrib.auth import get_user_model
from drf_spectacular.utils import extend_schema
from ..models import WorkSpace, WorkSpaceMember, Invitation
from ..serializers import WorkSpaceSerializer,WorkSpaceCreateSerializer
from ..permissions import IsCreatorOrReadOnly
from ..utils import notify_existing_user, notify_new_user
from users.views.invitations import InvitationViewSet
from django.db.models import Case, When, Value, BooleanField
from drf_spectacular.utils import extend_schema, extend_schema_view
from rest_framework.decorators import action

@extend_schema_view(
        list=extend_schema(tags=['فضاءات العمل'], summary="عرض فضاءات العمل الخاصة بالمستخدم مرتبة حسب التثبيت"),
        create=extend_schema(tags=['فضاءات العمل'], summary="إنشاء فضاء عمل جديد"),
        retrieve=extend_schema(tags=['فضاءات العمل'], summary="جلب تفاصيل فضاء عمل محدد"),
        update=extend_schema(tags=['فضاءات العمل'], summary="(للمدير)تحديث  كامل لفضاء العمل", description="هذا الاخيار يجب ان يظهر للمدير فقط"),
        destroy=extend_schema(tags=['فضاءات العمل'], summary="(للمدير)حذف فضاء العمل", description="هذا الاخيار يجب ان يظهر للمدير فقط")
)
class WorkspaceViewSet(viewsets.ModelViewSet):
        permission_classes = [permissions.IsAuthenticated, IsCreatorOrReadOnly]

        def get_queryset(self):
                user = self.request.user
                return WorkSpace.objects.filter(members=user).annotate(
                user_pinned=Case(
                        When(workspacemember__user=user, workspacemember__is_pinned=True, then=Value(True)),
                        default=Value(False),
                        output_field=BooleanField(),
                )
        ).order_by('-user_pinned', '-id').distinct()
        def get_serializer_class(self):

                if self.action in ['create', 'update', 'partial_update']:
                        return WorkSpaceCreateSerializer

                return WorkSpaceSerializer

        def perform_update(self, serializer):
                                workspace = serializer.save()
                                self.handle_invitations(workspace)

        def perform_create(self, serializer):
                workspace = serializer.save(creator=self.request.user)

                WorkSpaceMember.objects.get_or_create(
                user=self.request.user,
                workspace=workspace,
                role='ADMIN',
                defaults={'is_pinned': True}
                )
                if self.request.data.get('member_emails') :

                        invitation_view = InvitationViewSet()
                        invitation_view.request = self.request

                        invitation_view.request.data['project_id'] = workspace.project.id
                        invitation_view.request.data['workspace_id'] = workspace.id

                        invitation_view.send_project_invitation(invitation_view.request)

        @extend_schema(
        tags=['فضاءات العمل'],
        summary="(للموظف) تثبيت أو إلغاء تثبيت فضاء العمل",
        description="تسمح للموظف العادي بتثبيت الفضاء في أعلى قائمته الشخصية أو إلغاء تثبيته")
        @action(detail=True, methods=['post'], url_path='toggle_pin')
        def toggle_pin(self, request, pk=None):
                workspace = self.get_object()

                member_setting = get_object_or_404(WorkSpaceMember, user=request.user, workspace=workspace)

                member_setting.is_pinned = not member_setting.is_pinned
                member_setting.save()
                return Response(
                {
                        "message": f"Workspace pin status updated successfully.",
                        "is_pinned": member_setting.is_pinned
                },
                status=status.HTTP_200_OK
                )

        @extend_schema(
                tags=['فضاءات العمل'],
                summary="(للموظف) مغادرة فضاء العمل",
                description="تسمح للموظف العادي بحذف نفسه ومغادرة فضاء العمل إذا لم يعد من الفريق، ولا يسمح للمالك بمغادرة فضائه بهذه الطريقة"
        )
        @action(detail=True, methods=['delete'], url_path='leave')
        def leave_workspace(self, request, pk=None):
                workspace = self.get_object()

                if workspace.creator == request.user:
                        return Response(
                        {"error": "As the creator, you cannot leave this workspace. You must delete it or transfer ownership."},
                        status=status.HTTP_400_BAD_REQUEST
                )

                member = get_object_or_404(WorkSpaceMember, user=request.user, workspace=workspace)
                member.delete()

                return Response(
                {"message": f"You have successfully left the workspace: '{workspace.name}'."},
                status=status.HTTP_200_OK
                )


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