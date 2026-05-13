# Generated manually for GED Enterprise Sprint 3.0

from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
        ("automacoes", "0010_searchaudit"),
    ]

    operations = [
        migrations.CreateModel(
            name="JobExecution",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("job_name", models.CharField(db_index=True, max_length=150)),
                ("status", models.CharField(choices=[("PENDING", "Pendente"), ("RUNNING", "Executando"), ("SUCCESS", "Sucesso"), ("FAILED", "Falhou")], db_index=True, default="PENDING", max_length=20)),
                ("payload", models.JSONField(blank=True, default=dict)),
                ("result", models.JSONField(blank=True, default=dict)),
                ("error", models.TextField(blank=True)),
                ("started_at", models.DateTimeField(blank=True, db_index=True, null=True)),
                ("finished_at", models.DateTimeField(blank=True, null=True)),
                ("duration_ms", models.PositiveIntegerField(default=0)),
                ("created_at", models.DateTimeField(auto_now_add=True, db_index=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                ("created_by", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name="automacoes_jobs", to=settings.AUTH_USER_MODEL)),
            ],
            options={
                "verbose_name": "Execução de job",
                "verbose_name_plural": "Execuções de jobs",
                "ordering": ["-created_at"],
                "indexes": [
                    models.Index(fields=["job_name", "status"], name="automacoes_job_name_status_idx"),
                    models.Index(fields=["status", "created_at"], name="automacoes_job_status_created_idx"),
                ],
            },
        ),
    ]
