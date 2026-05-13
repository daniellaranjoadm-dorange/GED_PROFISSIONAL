# Generated manually for GED Scheduler State foundation

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("automacoes", "0012_alter_jobexecution_options_and_more"),
    ]

    operations = [
        migrations.CreateModel(
            name="SchedulerState",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("job_name", models.CharField(db_index=True, max_length=255, unique=True)),
                ("enabled", models.BooleanField(db_index=True, default=True)),
                ("last_run_at", models.DateTimeField(blank=True, null=True)),
                ("next_run_at", models.DateTimeField(blank=True, null=True)),
                ("last_success_at", models.DateTimeField(blank=True, null=True)),
                ("last_failure_at", models.DateTimeField(blank=True, null=True)),
                (
                    "last_status",
                    models.CharField(
                        choices=[
                            ("IDLE", "Idle"),
                            ("RUNNING", "Running"),
                            ("SUCCESS", "Success"),
                            ("FAILED", "Failed"),
                            ("DISABLED", "Disabled"),
                        ],
                        db_index=True,
                        default="IDLE",
                        max_length=20,
                    ),
                ),
                ("heartbeat_at", models.DateTimeField(blank=True, null=True)),
                ("runtime_notes", models.TextField(blank=True)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
            ],
            options={
                "ordering": ["job_name"],
                "indexes": [
                    models.Index(fields=["enabled", "last_status"], name="automacoes__enabled_2d3166_idx"),
                    models.Index(fields=["heartbeat_at"], name="automacoes__heartbe_7a2fd7_idx"),
                    models.Index(fields=["next_run_at"], name="automacoes__next_ru_2ba60b_idx"),
                ],
            },
        ),
    ]
