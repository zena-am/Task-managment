from django.db.models.signals import post_save, post_delete, pre_delete, pre_save
from django.dispatch import receiver
from .models import User, Task, ActivityLog, Notification,WorkSpaceMember,ProjectRole





@receiver(post_save, sender=Task)
def create_task_notification(sender, instance, created, **kwargs):
    if created and instance.assigned_to:
        assignee = instance.assigned_to
        project = instance.project

        Notification.objects.create(
            recipient=assignee,
            notification_type='TASK_ASSIGNED',
            title="New Task Assigned",
            message=f"Task '{instance.title}' has been assigned to you in project '{project.name}'.",
            navigation_target=f"/task_details/{instance.id}"
        )

        ActivityLog.objects.create(
            user=assignee,
            action='TASK_ASSIGNED',
            action_id=instance.id,
            changes={
                    "subject_name": assignee.username,
                    "target_title": instance.title,
                    "reason": f"Task was successfully assigned to {assignee.username} in project {project.name}.",
                    "is_by_admin": False
                        }
        )

        admins = ProjectRole.objects.filter(project=project, role='ADMIN').exclude(user=assignee)

        for admin_record in admins:
            admin_user = admin_record.user

            Notification.objects.create(
                recipient=admin_user,
                notification_type='TASK_ASSIGNED',
                title="Task Assignment Update",
                message=f"Task '{instance.title}' has been successfully assigned to {assignee.username}.",
                navigation_target=f"/task_details/{instance.id}"
            )

            ActivityLog.objects.create(
                user=admin_user,
                action='GENERAL_UPDATE',
                action_id=instance.id,
                changes={
                    "subject_name": assignee.username,
                    "email": assignee.email,
                    "target_title": instance.title,
                    "reason": f"Task was successfully assigned to {assignee.username} in project {project.name}.",
                    "is_by_admin": False

                }
            )
##################################################################################################################

#####################################################################################الغاء مهمة او اعادة تعيين المدير لها
#### setattr(task, 'is_being_kicked', True)
@receiver(pre_save, sender=Task)
def notify_on_task_unassignment(sender, instance, **kwargs):


    if not instance.pk:
        return
    try:
        previous_task = Task.objects.get(pk=instance.pk)
    except Task.DoesNotExist:
        return

    if previous_task.assigned_to and not instance.assigned_to:
        former_assignee = previous_task.assigned_to
        project = instance.project
        admins = ProjectRole.objects.filter(project=project, role='ADMIN').exclude(user=former_assignee)
        is_kicked = getattr(instance, 'is_being_kicked', False)
        user_reason = f"You were removed from the task '{instance.title}' by the manager. "if is_kicked else  f"You stepped down voluntarily from the task '{instance.title}'."
        if is_kicked:

            Notification.objects.create(
                    recipient=former_assignee,
                    notification_type='TASK_UNASSIGNED',
                    title="Task Assignment Update",
                    message=f"The manager has removed you from the task: '{instance.title}'.",
                    navigation_target="/my_tasks",
                )
        ActivityLog.objects.create(
                user=former_assignee,
                action="TASK_UNASSIGNED",
                action_id=instance.id,
                changes={
                "subject_name": former_assignee.username,
                "target_title": instance.title,
                "reason": user_reason,
                "is_by_admin": is_kicked
                }
        )

        for admin_member in admins:
            admin_user = admin_member.user
            if is_kicked:
                    Notification.objects.create(
                    recipient=admin_user,

                    notification_type='TASK_UNASSIGNED',
                    title="Task Assignment Update",
                    message=f"You have successfully removed '{former_assignee.username}' from the task: '{instance.title}'.",
                    navigation_target="/my_tasks")
            else:
                    Notification.objects.create(
                        recipient=admin_user,
                        notification_type='TASK_UNASSIGNED',
                        title="Member Left Task",
                        message=f"Member {former_assignee.username} has stepped down from the task: '{instance.title}'.",
                        navigation_target=f"/task_details/{instance.id}")

            log_reason = f"Manager removed {former_assignee.username} from task '{instance.title}'." if is_kicked else f"{former_assignee.username} stepped down from task '{instance.title}'."
            ActivityLog.objects.create(
                    user=admin_user,
                    action="TASK_UNASSIGNED",
                    action_id=instance.id,
                    changes={
                    "subject_name": former_assignee.username,
                    "target_title": instance.title,
                    "reason": log_reason,
                    "is_by_admin": is_kicked
                    }
            )

######################################################################مغادرة مساحة عمل ب
@receiver(post_delete, sender=WorkSpaceMember)
def notify_workspace_manager_on_leave(sender, instance, **kwargs):
        workspace = instance.workspace
        target_user = instance.user
        user_role = instance.role
        is_kicked = getattr(instance, 'is_being_kicked', False)

        admins = WorkSpaceMember.objects.filter(workspace=workspace, role='ADMIN').exclude(user=target_user)
        user_reason = f"Your membership in workspace '{workspace.name}' was terminated by the administrator."if is_kicked else f"You have voluntarily left the workspace '{workspace.name}'."

        if user_role == 'MANAGER':
            user_reason = f"Your manager status in workspace '{workspace.name}' was terminated." if is_kicked else f"You stepped down from managing workspace '{workspace.name}'."
            manager_reason = f"Manager '{target_user.username}' was removed from workspace '{workspace.name}'." if is_kicked else f"Manager '{target_user.username}' has voluntarily left workspace '{workspace.name}'."
            alert_title = "Workspace Manager Left"
        else:
            user_reason = f"Your membership in workspace '{workspace.name}' was terminated." if is_kicked else f"You have voluntarily left the workspace '{workspace.name}'."
            manager_reason = f"Member {target_user.username} has been removed from {workspace.name}." if is_kicked else f"Member {target_user.username} has voluntarily left {workspace.name}."
            alert_title = "Member Left" if not is_kicked else "Member Removed"

        if is_kicked:
            Notification.objects.create(
        recipient=target_user,
        notification_type='SYSTEM_ALERT',
        title="Workspace Membership Updated",
        message=f"Your membership in workspace '{instance.workspace.name}' has been terminated by the administrator.",
        navigation_target="/home")

        ActivityLog.objects.create(
        user=target_user,
        action="MEMBER_REMOVED" if is_kicked else "MEMBER_LEFT",
        action_id=workspace.id,
        changes={
            "subject_name": target_user.username,
            "target_title": workspace.name,
            "reason": user_reason,
            "is_by_admin": is_kicked
        }
    )


        for admin_member in admins:
            admin_user = admin_member.user

            Notification.objects.create(
                    recipient=admin_user,
                    notification_type='SYSTEM_ALERT',
                    title="Member Removed",
                    message=manager_reason,
                    navigation_target=f"/workspace_details/{workspace.id}"
        )

            ActivityLog.objects.create(
                user=admin_user,
                action="MEMBER_REMOVED" if is_kicked else "MEMBER_LEFT",
                action_id=instance.workspace.id,
                changes={
                "subject_name": target_user.username,
                "target_title": workspace.name,
                "reason": manager_reason,
                "is_by_admin": is_kicked})


######################################################################مغادرة مشروع ب
@receiver(post_delete, sender=ProjectRole)
def notify_project_manager_on_leave(sender, instance, **kwargs):
        project = instance.project
        target_user = instance.user
        user_role = instance.role
        is_kicked = getattr(instance, 'is_being_kicked', False)

        if user_role == 'MANAGER':
            admins = WorkSpaceMember.objects.filter(workspace=project.workspace, role='ADMIN')
        else:
            admins = ProjectRole.objects.filter(project=project, role='ADMIN').exclude(user=target_user)


        if user_role == 'MANAGER':
            user_reason = f"Your management role in project '{project.name}' was terminated." if is_kicked else f"You have stepped down from managing the project '{project.name}'."
            manager_reason = f"Manager '{target_user.username}' was removed from project '{project.name}'." if is_kicked else f"Manager '{target_user.username}' has voluntarily left the project '{project.name}'."
            alert_title = "Project Manager Left" if not is_kicked else "Project Manager Removed"
        else:
            user_reason = f"Your membership in project '{project.name}' was terminated by the administrator." if is_kicked else f"You have voluntarily left the project '{project.name}'."
            manager_reason = f"Member {target_user.username} has been removed from project '{project.name}'." if is_kicked else f"Member {target_user.username} has voluntarily left project '{project.name}'."
            alert_title = "Member Left" if not is_kicked else "Member Removed"

        if is_kicked:
            Notification.objects.create(
        recipient=target_user,
        notification_type='SYSTEM_ALERT',
        title="Project Access Updated",
        message=user_reason,
        navigation_target="/home")

        ActivityLog.objects.create(
        user=target_user,
        action="MEMBER_REMOVED" if is_kicked else "MEMBER_LEFT",
        action_id=project.id,
        changes={
            "subject_name": target_user.username,
            "target_title": project.name,
            "reason": user_reason,
            "is_by_admin": is_kicked
        }
    )

        for admin_member in admins:
            admin_user = admin_member.user

            Notification.objects.create(
                    recipient=admin_user,
                    notification_type='SYSTEM_ALERT',
                    title=alert_title,
                    message=manager_reason,
                    navigation_target=f"/workspace_details/{project.id}"
        )

            ActivityLog.objects.create(
                user=admin_user,
                action="MEMBER_REMOVED" if is_kicked else "MEMBER_LEFT",
                action_id=project.id,
                changes={
                "subject_name": target_user.username,
                "target_title": project.name,
                "reason": manager_reason,
                "is_by_admin": is_kicked}
                    )





##############################################################################3حذف كامل من النظام
@receiver(pre_delete, sender=User)
def notify_managers_on_account_deletion(sender, instance, **kwargs):

    user_workspaces_role = instance.workspacemember_set.select_related('workspace')

    for member in user_workspaces_role:
        current_workspace = member.workspace

        workspace_admins = WorkSpaceMember.objects.filter(workspace=current_workspace, role='ADMIN').exclude(user=instance)

        for ws_admin in workspace_admins:
            Notification.objects.create(
                recipient=ws_admin.user,
                notification_type='SYSTEM_ALERT',
                title="Workspace Member Deleted",
                message=f"User '{instance.username}' has been removed from the system. Impacted Workspace: {current_workspace.name}.",
                navigation_target=f"/workspace_details/{current_workspace.id}"
            )

            ActivityLog.objects.create(
                user=ws_admin.user,
                action="ACCOUNT_PURGED",
                action_id=current_workspace.id,
                changes={
                    "subject_name": instance.username,
                    "target_title": current_workspace.name,  # الهدف هنا هو اسم الفضاء
                    "reason": f"The account of user '{instance.username}' was deleted from the system, removing them from the workspace.",
                    "is_by_admin": False
                }
            )



    user_project_roles = instance.projectrole_set.all()



    for user_role in user_project_roles:
        current_project = user_role.project
        current_workspace=user_role.project.workspace

        admins = ProjectRole.objects.filter(project=current_project,role='ADMIN' ).exclude(user=instance)

        for admin_record in admins:

            Notification.objects.create(
                recipient=admin_record.user,
                notification_type='SYSTEM_ALERT',
                title="Member Account Deleted",
                message=f"User '{instance.username}' has been removed from the system. Impacted Project: {current_project.name}.",
                navigation_target=f"/project_details/{current_project.id}"
            )

            ActivityLog.objects.create(
                user=admin_record.user,
                action="ACCOUNT_PURGED",
                action_id=current_project.id,
                changes={
                    "subject_name": instance.username,
                    "target_title": current_project.name,
                    "reason": f"The account of user '{instance.username}' was completely deleted from the system.",
                    "is_by_admin": False
                }
            )



@receiver(post_save, sender=Task)
def update_project_status_on_task_change(sender, instance, **kwargs):
    project = instance.project
    if project.status == 'pending':
        project.status = 'on_going'
        project.save()

    elif project.status == 'on_going':
        total_tasks = project.task_set.count()

        completed_tasks = project.task_set.filter(status='done').count()

        if total_tasks > 0 and total_tasks == completed_tasks:
            project.status = 'completed'
            project.save()





        """@receiver(post_save, sender=User)
def create_profile(sender, instance, created, **kwargs):
    if created:
        Profile.objects.create(user=instance)
        ActivityLog.objects.create(
            user=instance,
            action='ACCOUNT_CREATED',
            action_id=instance.id,
            changes={
                "subject_name": instance.username,
                "email": instance.email,
                "target_title": "system",
                "reason": "User profile has been automatically initialized.",
                "is_by_admin": False
            }
        )
"""