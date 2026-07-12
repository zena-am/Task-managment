from django.test import TestCase

from users.errors.exceptions import AccountAlreadyDeletedError, AccountIsLastProjectManagerError, AccountOwnsWorkspacesError
from users.models import Invitation, Project, ProjectRole, Task, User, WorkSpace, WorkSpaceMember
from users.services.user_service import UserService


class UserSoftDeleteTests(TestCase):
    def setUp(self):
        self.owner = User.all_objects.create_user(
            username="owner", email="owner@example.com", password="pass12345"
        )
        self.member = User.all_objects.create_user(
            username="member", email="member@example.com", password="pass12345"
        )
        self.workspace = WorkSpace.objects.create(
            creator=self.owner, name="Workspace", description="Description"
        )
        WorkSpaceMember.objects.create(
            workspace=self.workspace, user=self.owner, role="ADMIN"
        )
        WorkSpaceMember.objects.create(
            workspace=self.workspace, user=self.member, role="MEMBER"
        )
        self.project = Project.objects.create(
            workspace=self.workspace, name="Project", description="Description"
        )
        ProjectRole.objects.create(
            project=self.project, user=self.member, role="EMPLOYEE"
        )
        self.task = Task.objects.create(
            creator=self.owner,
            project=self.project,
            title="Active Task",
            description="Description",
            expected_duration="01:00:00",
            due_date="2027-01-01T00:00:00Z",
            assigned_to=self.member,
            status="INPROGRESS",
        )
        self.completed_task = Task.objects.create(
            creator=self.owner,
            project=self.project,
            title="Completed Task",
            description="Description",
            expected_duration="01:00:00",
            due_date="2027-01-01T00:00:00Z",
            assigned_to=self.member,
            status="DONE",
        )

    def test_soft_delete_deactivates_and_hides_user(self):
        UserService.soft_delete_account(self.member)

        deleted_user = User.all_objects.get(pk=self.member.pk)
        self.assertTrue(deleted_user.is_deleted)
        self.assertFalse(deleted_user.is_active)
        self.assertIsNotNone(deleted_user.deleted_at)
        self.assertFalse(User.objects.filter(pk=self.member.pk).exists())
        self.assertFalse(ProjectRole.objects.filter(user_id=self.member.pk).exists())
        self.assertFalse(WorkSpaceMember.objects.filter(user_id=self.member.pk).exists())

        self.task.refresh_from_db()
        self.assertIsNone(self.task.assigned_to_id)
        self.assertEqual(self.task.assignment_state, "UNASSIGNED_RETURNED")

        self.completed_task.refresh_from_db()
        self.assertEqual(self.completed_task.assigned_to_id, self.member.id)
        self.assertEqual(self.completed_task.status, "DONE")
        self.assertEqual(self.completed_task.assignment_state, "ASSIGNED")

    def test_workspace_owner_must_transfer_ownership_first(self):
        with self.assertRaises(AccountOwnsWorkspacesError):
            UserService.soft_delete_account(self.owner)

    def test_pending_invitation_is_rejected(self):
        invitation = Invitation.objects.create(
            sender=self.owner,
            receiver=self.member,
            receiver_email=self.member.email,
            workspace=self.workspace,
            role="MEMBER",
            status="PENDING",
        )
        UserService.soft_delete_account(self.member)
        invitation.refresh_from_db()
        self.assertEqual(invitation.status, "REJECTED")

    def test_soft_delete_is_not_repeatable(self):
        UserService.soft_delete_account(self.member)
        deleted = User.all_objects.get(pk=self.member.pk)
        with self.assertRaises(AccountAlreadyDeletedError):
            UserService.soft_delete_account(deleted)

    def test_last_project_manager_must_be_replaced(self):
        manager = User.all_objects.create_user(
            username="manager", email="manager@example.com", password="pass12345"
        )
        WorkSpaceMember.objects.create(workspace=self.workspace, user=manager, role="MEMBER")
        ProjectRole.objects.create(project=self.project, user=manager, role="MANAGER")
        with self.assertRaises(AccountIsLastProjectManagerError):
            UserService.soft_delete_account(manager)
