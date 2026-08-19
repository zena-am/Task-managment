from django.db import migrations


def fill_assigned_at(apps, schema_editor):
    Task = apps.get_model(
        "users",
        "Task"
    )

    tasks = Task.objects.filter(
        assigned_to__isnull=False,
        assigned_at__isnull=True,
    )

    for task in tasks:
        task.assigned_at = task.created_at
        task.save(
            update_fields=[
                "assigned_at"
            ]
        )


class Migration(migrations.Migration):

    dependencies = [
        ('users', '0018_task_assigned_at'),
    ]

    operations = [
        migrations.RunPython(
            fill_assigned_at,
            migrations.RunPython.noop,
        ),
    ]