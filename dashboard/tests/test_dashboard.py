from datetime import timedelta

from django.urls import reverse
from django.utils import timezone
from rest_framework.test import APITestCase

from users.models import Project, ProjectRole, Task, User, WorkSpace, WorkSpaceMember


class ManagerDashboardTests(APITestCase):
    def setUp(self):
        self.manager = User.objects.create_user(
            username="manager",
            email="manager@example.com",
            password="pass12345",
        )
        self.workspace = WorkSpace.objects.create(
            creator=self.manager,
            name="Workspace",
            description="Test workspace",
        )
        WorkSpaceMember.objects.create(
            user=self.manager,
            workspace=self.workspace,
            role="ADMIN",
        )
        self.project = Project.objects.create(
            workspace=self.workspace,
            name="Project",
            description="Test project",
            status="on_going",
        )
        ProjectRole.objects.create(
            project=self.project,
            user=self.manager,
            role="MANAGER",
        )
        Task.objects.create(
            creator=self.manager,
            project=self.project,
            title="Task",
            description="Test task",
            expected_duration=timedelta(hours=1),
            due_date=timezone.now() + timedelta(days=1),
        )
        self.client.force_authenticate(self.manager)

    def test_overview_is_available_to_manager(self):
        response = self.client.get(reverse("dashboard:overview"))
        self.assertEqual(response.status_code, 200)

    def test_activity_is_available_to_manager(self):
        response = self.client.get(reverse("dashboard:activity"))
        self.assertEqual(response.status_code, 200)
