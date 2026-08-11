import django.db.models.deletion
from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("automacoes", "0023_execucaoautomacao_audit_context"),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]
    operations = [
        migrations.CreateModel(
            name="AutomationExecutionLock",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("nome", models.CharField(max_length=100, unique=True)),
                ("token", models.UUIDField(editable=False, unique=True)),
                ("adquirido_em", models.DateTimeField(auto_now_add=True)),
                ("expira_em", models.DateTimeField(db_index=True)),
                ("usuario", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name="bloqueios_automacoes", to=settings.AUTH_USER_MODEL)),
            ],
            options={
                "verbose_name": "Bloqueio de execução de automação",
                "verbose_name_plural": "Bloqueios de execução de automações",
                "ordering": ["nome"],
            },
        ),
    ]
