from rest_framework import viewsets, mixins, permissions, status
from rest_framework.decorators import action
from rest_framework.response import Response
from django.contrib.auth import get_user_model
from django.db import transaction
from drf_spectacular.utils import extend_schema
from ..models import Project
from ..models import Invitation, WorkSpaceMember, ProjectRole,WorkSpace
from ..serializers import InvitationSerializer
from ..utils import notify_existing_user, notify_new_user

@extend_schema(tags=['دعوة أعضاء'])
class InvitationViewSet( mixins.RetrieveModelMixin, mixins.ListModelMixin, mixins.CreateModelMixin,viewsets.GenericViewSet ):
    queryset = Invitation.objects.all()
    serializer_class = InvitationSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        return Invitation.objects.filter(receiver_email=self.request.user.email)

    @extend_schema(
        summary="جلب قائمة الدعوات الخاصة بالمستخدم",
        description="يعيد هذا الرابط قائمة بجميع الدعوات التي أُرسلت للمستخدم الحالي (بناءً على بريده الإلكتروني). تُستخدم هذه القائمة لعرض الطلبات المعلقة في واجهة التطبيق.",
    )
    def list(self, request, *args, **kwargs):
        return super().list(request, *args, **kwargs)


    @extend_schema(
        summary="جلب تفاصيل دعوة محددة",
        description="يستقبل معرف الدعوة (ID) ويعيد كافة التفاصيل المتعلقة بها، مثل اسم المرسل، مساحة العمل، المشروع، والدور المقترح.",
    )
    def retrieve(self, request, *args, **kwargs):
        return super().retrieve(request, *args, **kwargs)

########################################################################دعوات الفضاء
    @extend_schema(
        summary="إرسال دعوة جديدة",
        description="يقوم بإرسال دعوة للانضمام لمساحة عمل عبر البريد الإلكتروني. إذا كان المستخدم مسجلاً، يتم إخطاره، وإذا لم يكن، يتم إرسال دعوة خارجية له",
        responses={201: InvitationSerializer},
    )
    @action(detail=False, methods=['post'])
    def send_workspace_invitation(self, request):
        User = get_user_model()
        email = request.data.get('email')
        project_id = request.data.get('project_id')
        role = request.data.get('role', 'MEMBER')
        workspace_id = request.data.get('workspace_id')

        if not email or not workspace_id:
            return Response(
                {"error": "Email and workspace_id are required."},
                status=status.HTTP_400_BAD_REQUEST
            )
        try:
            workspace = WorkSpace.objects.get(id=workspace_id)
        except WorkSpace.DoesNotExist:
            return Response({"error": "Workspace not found."}, status=status.HTTP_404_NOT_FOUND)

        sender_name = request.user.get_full_name() or request.user.username
        workspace_name = workspace.name

        existing_invitation = Invitation.objects.filter(receiver_email=email, workspace_id=workspace_id, project_id=project_id).first()
        if existing_invitation:
            if existing_invitation.status == 'ACCEPTED':
                return Response({"detail": "This user is already a member."}, status=status.HTTP_400_BAD_REQUEST)
            existing_invitation.status = 'PENDING'
            existing_invitation.sender = request.user
            existing_invitation.role = role
            existing_invitation.save()
            notify_existing_user(email, sender_name, workspace_name)
            return Response({"detail": "Invitation resent and updated."})

        receiver = User.objects.filter(email=email).first()


        if receiver:
            invitation = Invitation.objects.create(
                sender=request.user,
                receiver=receiver,
                receiver_email=email,
                project_id=project_id,
                workspace_id=workspace_id,
                role=role,
                status='PENDING'
            )
            notify_existing_user(email, sender_name, workspace_name)
            return Response({"detail": "Invitation sent successfully."}, status=201)
        else:

            invitation = Invitation.objects.create(
                sender=request.user,
                receiver_email=email,
                project_id=project_id,
                workspace_id=workspace_id,
                role=role,
                status='PENDING'
            )
            notify_new_user(email, sender_name, workspace_name)

            return Response({"detail": "Invitation sent successfully."}, status=status.HTTP_201_CREATED)
########################################################################دعوات للمشروع
    @extend_schema(
        summary="  إرسال دعوة جديدة للمشروع",
        description="يقوم بإرسال دعوة للانضمام  للمشروع عبر البريد الإلكتروني. إذا كان المستخدم مسجلاً في الفضاء او موجود بالتطبيق بشكل عام، يتم إخطاره، وإذا لم يكن، يتم إرسال دعوة خارجية له",
        responses={201: InvitationSerializer},
    )
    @action(detail=False, methods=['post'])
    def send_project_invitation(self, request):
        User = get_user_model()
        member_emails = self.request.data.get('member_emails', [])
        if isinstance(member_emails, str):
            member_emails = [member_emails]

        project_id = request.data.get('project_id')
        role = request.data.get('role', 'MEMBER')
        workspace_id = request.data.get('workspace_id')

        try:
            project = Project.objects.get(id=project_id)
        except Project.DoesNotExist:
            return Response({"error": "Project not found."}, status=status.HTTP_404_NOT_FOUND)
        if not project_id:
            return Response({"error": "project_id is required."}, status=status.HTTP_400_BAD_REQUEST)

        members_ids = self.request.data.get('members_ids', [])

        if members_ids:
            for user_id in members_ids:
                try:
                    user_to_add = User.objects.get(id=user_id)
                    is_workspace_member = WorkSpaceMember.objects.filter(workspace=project.workspace,user=user_to_add ).exists()

                    if is_workspace_member:
                            WorkSpaceMember.objects.get_or_create(
                                workspace=project.workspace,
                                user=user_to_add,
                                defaults={'role': 'EMPLOYEE'}
                            )

                            ProjectRole.objects.get_or_create(
                                project=project,
                                user=user_to_add,
                                defaults={'role': 'DEV'}
                            )
                    else:

                        continue
                except User.DoesNotExist:
                    continue
        User = get_user_model()
        sender_name = self.request.user.get_full_name() or self.request.user.username
        workspace_name = project.workspace.name
        role = self.request.data.get('role', 'DEV')
        workspace = project.workspace

        for email in member_emails:
            existing_invitation = Invitation.objects.filter(receiver_email=email,workspace=project.workspace,project=project).first()
            if existing_invitation is not None:
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

                Invitation.objects.create(
                    sender=self.request.user,
                    receiver=receiver,
                    receiver_email=email,
                    workspace=workspace,
                    project=project,
                    role=role,
                    status='PENDING'
                )

                notify_existing_user(email, sender_name, workspace_name)

            else:

                invitation = Invitation.objects.create(
                sender=self.request.user,
                receiver_email=email,
                project=project,
                workspace=project.workspace,
                role=role,
                status='PENDING')
                notify_new_user(email, sender_name, workspace_name)



        return Response({"detail": "Project invitations and additions processed successfully."}, status=status.HTTP_201_CREATED)










###################################################accept
    @extend_schema(
        summary="قبول دعوة",
        description="يسمح للمستخدم بقبول الدعوة الموجهة إليه. عند القبول، يتم إضافة المستخدم تلقائياً كعضو في مساحة العمل (وفي المشروع إن وجد) وتتغير حالة الدعوة إلى مقبول  ",
        responses={200: {"detail": "You have successfully joined..."}},
    )
    @action(detail=True, methods=['post'])
    def accept(self, request, pk=None):
        invitation = self.get_object()



        if invitation.receiver_email != request.user.email:
            return Response(
                {"error": "This invitation was not sent to your email address."},
                status=status.HTTP_403_FORBIDDEN
            )

        with transaction.atomic():
            WorkSpaceMember.objects.get_or_create(
                workspace=invitation.workspace,
                user=request.user,
                defaults={'role': invitation.role}
            )


            if invitation.project:
                ProjectRole.objects.get_or_create(
                    project=invitation.project,
                    user=request.user,
                    defaults={
                        'role': 'DEV'
                        }
                )

            invitation.status = 'ACCEPTED'
            invitation.save()

        return Response(
            {"detail": "You have successfully joined the workspace/project."},
            status=status.HTTP_200_OK
        )

###################################################reject
    @extend_schema(
        summary="رفض دعوة",
        description="يسمح للمستخدم برفض الدعوة الموجهة إليه، مما يؤدي لتغيير حالة الدعوة إلى  ومنعه من الانضمام عبر هذا الرابط.",
        responses={200: {"detail": "Invitation rejected successfully"}},
    )
    @action(detail=True, methods=['post'])
    def reject(self, request, pk=None):
        invitation = self.get_object()
        if invitation.receiver_email != request.user.email:
            return Response(
                {"error": "You do not have permission to reject this invitation."},
                status=status.HTTP_403_FORBIDDEN
            )

        invitation.status = 'REJECTED'
        invitation.receiver = request.user
        invitation.save()

        return Response({"detail": "Invitation rejected successfully."})