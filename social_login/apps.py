from django.apps import AppConfig


class SocialLoginConfig(AppConfig):
    name = 'social_login'

class UsersConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'users'

    def ready(self):

        import users.signals