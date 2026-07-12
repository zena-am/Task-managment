from django.contrib.auth.models import UserManager


class ActiveUserManager(UserManager):
    """Default manager: hide accounts that were soft-deleted."""

    use_in_migrations = True

    def get_queryset(self):
        return super().get_queryset().filter(is_deleted=False)

    def active(self):
        return self.get_queryset().filter(is_active=True)
