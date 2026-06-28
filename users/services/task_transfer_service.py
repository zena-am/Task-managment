from rest_framework.exceptions import ValidationError

from users.constants import create_activity_log
from users.models import Notification, Project, ProjectRole, Task, User


class TaskTransferService:

    @staticmethod
    def get_orphaned_tasks(project):
        return Task.objects.filter(project=project, assigned_to__isnull=True)


    @staticmethod
    def assign_unassigned_tasks(project, new_assignee):
        tasks = Task.objects.filter(
            project=project,
            assigned_to__isnull=True
        )

        count = tasks.count()

        if count == 0:
            return 0

        tasks.update(assigned_to=new_assignee, status="TODO")

        return count

    @staticmethod
    def assign_task_to_user(task, new_assignee, performed_by,project):
        task.assigned_to = new_assignee
        task.status = "TODO"
        task.save(update_fields=["assigned_to", "status", "updated_at"])

        create_activity_log(
            user=performed_by,
            action="GENERAL_UPDATE",
            action_id=task.id,
            changes={"new_assignee": new_assignee.username}
        )
        Notification.objects.create(
        recipient=new_assignee,
        notification_type="SYSTEM_ALERT",
        title="New Task Assigned",
        message=f"You have been assigned to task '{task.title}' in project '{project.name}'.",
        navigation_target=f"/tasks/{task.id}"
        )


class ProjectService:

    @staticmethod
    def get_projects_without_manager():

        managed_projects_ids = ProjectRole.objects.filter(role__in=["MANAGER", "ADMIN"]).values_list("project_id", flat=True)

        unmanaged_projects = Project.objects.exclude(id__in=managed_projects_ids)

        return unmanaged_projects


    @staticmethod
    def assign_new_manager(project, new_manager, performed_by):

        project_role = ProjectRole.objects.filter(
            project=project,
            user=new_manager
        ).first()

        if not project_role:
            raise ValidationError(
                "User is not a member of this project."
            )

        project_role.role = "MANAGER"
        project_role.save(update_fields=["role"])

        create_activity_log(
            user=performed_by,
            action="ROLE_UPDATED",
            action_id=project.id,
            changes={
                "subject_name": new_manager.username,
                "target_title": project.name,
                "reason": f"{new_manager.username} was assigned as manager of project {project.name}.",
                "is_by_admin": True
            }
        )

        Notification.objects.create(
            recipient=new_manager,
            notification_type="SYSTEM_ALERT",
            title="Project Manager Assigned",
            message=f"You have been assigned as manager of project '{project.name}'.",
            navigation_target=f"/projects/{project.id}"
        )


        return project_role




class RoleService:
    @staticmethod
    def set_user_role(project, user, new_role, performed_by):
        project_role, created = ProjectRole.objects.get_or_create(project=project,user=user)

        if not project_role:
            raise ValidationError(
                "User is not a member of this project."
            )

        old_role = project_role.role

        project_role.role = new_role
        project_role.save(update_fields=["role"])
        project_role.save()

        create_activity_log(
            user=performed_by,
            action="ROLE_UPDATED",
            action_id=project.id,
            changes={
                "user": user.username,
                "old_role": old_role,
                "new_role": new_role
            }
        )
        create_activity_log(
            user=user,
            action="ROLE_UPDATED",
            action_id=project.id,
            changes={
                "user": user.username,
                "old_role": old_role,
                "new_role": new_role
            }
        )
        Notification.objects.create(
            recipient=user,
            notification_type="SYSTEM_ALERT",
            title="Project Manager Assigned",
            message=f"You have been assigned as manager of project '{project.name}'.",
            navigation_target=f"/projects/{project.id}"
        )
        return project_role




    @staticmethod
    def transfer_tasks(project, new_assignee, performed_by):
        tasks = Task.objects.filter(project=project, assigned_to__isnull=True)
        count = tasks.count()

        if count == 0:
            return 0

        task_ids = list(tasks.values_list('id', flat=True))
        tasks.update(assigned_to=new_assignee, status="TODO")

        create_activity_log(
            user=performed_by,
            action="GENERAL_UPDATE",
            action_id=project.id,
            changes={
                "subject_name": new_assignee.username,
                "target_title": f"Project {project.name}",
                "reason": f"{count} unassigned tasks transferred to {new_assignee.username}",
                "is_by_admin": True,
                "task_ids": task_ids,
            }
        )

        for task_id in task_ids:
            Notification.objects.create(
                recipient=new_assignee,
                notification_type="SYSTEM_ALERT",
                title="Assigned Task",
                message=f"You have been assigned a task in project '{project.name}'.",
                navigation_target=f"/task_details/{task_id}"
            )

        return count
