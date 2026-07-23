from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):
    dependencies = [
        ("users", "0003_task_deleted_at_task_deleted_by_task_is_deleted"),
    ]

    operations = [
        migrations.AddField(model_name="workspace", name="is_archived", field=models.BooleanField(db_index=True, default=False)),
        migrations.AddField(model_name="workspace", name="archived_at", field=models.DateTimeField(blank=True, null=True)),
        migrations.AddField(model_name="workspace", name="archived_by", field=models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name="archived_workspaces", to=settings.AUTH_USER_MODEL)),
        migrations.AddField(model_name="project", name="is_archived", field=models.BooleanField(db_index=True, default=False)),
        migrations.AddField(model_name="project", name="archived_at", field=models.DateTimeField(blank=True, null=True)),
        migrations.AddField(model_name="project", name="archived_by", field=models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name="archived_projects", to=settings.AUTH_USER_MODEL)),
        migrations.AddField(model_name="task", name="is_archived", field=models.BooleanField(db_index=True, default=False)),
        migrations.AddField(model_name="task", name="archived_at", field=models.DateTimeField(blank=True, null=True)),
        migrations.AddField(model_name="task", name="archived_by", field=models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name="archived_tasks", to=settings.AUTH_USER_MODEL)),
    ]
