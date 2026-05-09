from django.db.models.signals import post_save,post_delete
from django.dispatch import receiver
from .models import User, Profile
from .models import Task, ActivityLog

@receiver(post_save, sender=User)
def create_profile(sender, instance, created, **kwargs):
    if created:
        Profile.objects.create(user=instance)



@receiver(post_delete, sender=User)
def notify_manager_on_user_delete(sender, instance, **kwargs):

    manager = User.objects.filter(is_staff=True).first()

    if manager:

        ActivityLog.objects.create(
            user=manager,
            action=f" تم حذف المستخدم {instance.username}. المهام الخاصة به بحاجة لإعادة تفويض."
        )