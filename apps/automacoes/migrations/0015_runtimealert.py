
from django.db import migrations, models

class Migration(migrations.Migration):

    dependencies = [
        ("automacoes", "0014_rename_automacoes__enabled_2d3166_idx_automacoes__enabled_a00976_idx_and_more"),
    ]

    operations = [
        migrations.CreateModel(
            name="RuntimeAlert",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("titulo", models.CharField(max_length=255)),
                ("codigo", models.CharField(db_index=True, max_length=100)),
                ("severidade", models.CharField(
                    choices=[
                        ("INFO", "Info"),
                        ("WARNING", "Warning"),
                        ("ERROR", "Error"),
                        ("CRITICAL", "Critical"),
                    ],
                    db_index=True,
                    default="WARNING",
                    max_length=20,
                )),
                ("job_name", models.CharField(blank=True, db_index=True, max_length=255)),
                ("mensagem", models.TextField()),
                ("detalhes", models.JSONField(blank=True, default=dict)),
                ("resolvido", models.BooleanField(db_index=True, default=False)),
                ("resolvido_em", models.DateTimeField(blank=True, null=True)),
                ("criado_em", models.DateTimeField(auto_now_add=True, db_index=True)),
            ],
            options={
                "ordering": ["-criado_em"],
                "indexes": [
                    models.Index(fields=["codigo", "resolvido"], name="automacoes__codigo_runtime_idx"),
                    models.Index(fields=["severidade", "criado_em"], name="automacoes__severity_runtime_idx"),
                ],
            },
        ),
    ]
