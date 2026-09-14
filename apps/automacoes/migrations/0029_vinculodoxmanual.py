from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):
    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
        ("automacoes", "0028_executivemetricsnapshot"),
    ]

    operations = [
        migrations.CreateModel(
            name="VinculoDoxManual",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("tipo", models.CharField(choices=[("DOCUMENTO", "Documento"), ("PCF", "PCF")], db_index=True, max_length=20)),
                ("identificador", models.CharField(max_length=255)),
                ("chave_normalizada", models.CharField(db_index=True, editable=False, max_length=255)),
                ("revisao", models.CharField(blank=True, default="", max_length=50)),
                ("url_dox", models.URLField(max_length=500)),
                ("ativo", models.BooleanField(default=True)),
                ("criado_em", models.DateTimeField(auto_now_add=True)),
                ("atualizado_em", models.DateTimeField(auto_now=True)),
                ("criado_por", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name="vinculos_dox_manuais", to=settings.AUTH_USER_MODEL)),
            ],
            options={"ordering": ["tipo", "identificador", "revisao"]},
        ),
        migrations.AddConstraint(
            model_name="vinculodoxmanual",
            constraint=models.UniqueConstraint(fields=("tipo", "chave_normalizada", "revisao"), name="uniq_vinculo_dox_manual_tipo_chave_revisao"),
        ),
    ]
