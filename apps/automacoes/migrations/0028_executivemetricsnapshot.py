from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [("automacoes", "0027_documentold_medicao_cronograma")]

    operations = [
        migrations.CreateModel(
            name="ExecutiveMetricSnapshot",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("origem", models.CharField(db_index=True, max_length=100)),
                ("data_referencia", models.DateField(db_index=True)),
                ("total", models.PositiveIntegerField(default=0)),
                ("emitidos", models.PositiveIntegerField(default=0)),
                ("vencidos_nao_emitidos", models.PositiveIntegerField(default=0)),
                ("vencendo_30_dias", models.PositiveIntegerField(default=0)),
                ("pcf_criticas", models.PositiveIntegerField(default=0)),
                ("pcf_aguardando_resposta", models.PositiveIntegerField(default=0)),
                ("comentarios_abertos", models.PositiveIntegerField(default=0)),
                ("aprovados_sem_ressalvas", models.PositiveIntegerField(default=0)),
                ("aderencia_prazo", models.FloatField(default=0)),
                ("progresso", models.FloatField(default=0)),
                ("qualidade_dados", models.FloatField(default=0)),
                ("metricas", models.JSONField(blank=True, default=dict)),
                ("capturado_em", models.DateTimeField(auto_now=True)),
            ],
            options={"ordering": ["-data_referencia", "origem"]},
        ),
        migrations.AddConstraint(
            model_name="executivemetricsnapshot",
            constraint=models.UniqueConstraint(
                fields=("origem", "data_referencia"),
                name="uniq_executive_snapshot_origem_data",
            ),
        ),
    ]
