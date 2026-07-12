from django.db import migrations, models
import django.contrib.auth.models
import users.managers


class Migration(migrations.Migration):

    dependencies = [
        ("users", "0002_remove_task_users_task_workspa_c56243_idx_and_more"),
    ]

    operations = [
        migrations.AddField(
            model_name="user",
            name="deleted_at",
            field=models.DateTimeField(blank=True, null=True),
        ),
        migrations.AddField(
            model_name="user",
            name="is_deleted",
            field=models.BooleanField(db_index=True, default=False),
        ),
        migrations.AlterModelManagers(
            name="user",
            managers=[
                ("objects", users.managers.ActiveUserManager()),
                ("all_objects", django.contrib.auth.models.UserManager()),
            ],
        ),
        migrations.AlterModelOptions(
            name="user",
            options={
                "base_manager_name": "all_objects",
                "default_manager_name": "objects",
            },
        ),
    ]
