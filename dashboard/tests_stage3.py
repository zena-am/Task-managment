from django.contrib.auth import get_user_model
from django.urls import reverse
from rest_framework.test import APITestCase

from users.models import Project, ProjectRole, Task, WorkSpace, WorkSpaceMember


class DashboardStage3Tests(APITestCase):
    def setUp(self):
        User = get_user_model()
        self.manager = User.objects.create_user(username="manager", email="manager@example.com", password="pass12345")
        self.employee = User.objects.create_user(username="employee", email="employee@example.com", password="pass12345")
        self.workspace = WorkSpace.objects.create(creator=self.manager, name="Workspace", description="Test")
        WorkSpaceMember.objects.create(user=self.manager, workspace=self.workspace, role="ADMIN")
        WorkSpaceMember.objects.create(user=self.employee, workspace=self.workspace, role="MEMBER")
        self.project = Project.objects.create(workspace=self.workspace, name="Project", description="Test")
        ProjectRole.objects.create(user=self.manager, project=self.project, role="MANAGER")
        ProjectRole.objects.create(user=self.employee, project=self.project, role="EMPLOYEE")
        self.client.force_authenticate(self.manager)

    def test_archive_project(self):
        url = reverse("dashboard:archive-action", kwargs={"resource": "project", "object_id": self.project.id})
        response = self.client.post(url, {"archive": True}, format="json")
        self.assertEqual(response.status_code, 200)
        self.project.refresh_from_db()
        self.assertTrue(self.project.is_archived)

    def test_export_csv(self):
        response = self.client.get(reverse("dashboard:export"), {"resource": "tasks", "format": "csv"})
        self.assertEqual(response.status_code, 200)
        self.assertIn("text/csv", response["Content-Type"])
