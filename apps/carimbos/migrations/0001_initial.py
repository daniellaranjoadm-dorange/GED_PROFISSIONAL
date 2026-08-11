# Generated manually for the controlled-copy traceability module.
import django.db.models.deletion
from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):
    initial = True
    dependencies = [migrations.swappable_dependency(settings.AUTH_USER_MODEL)]
    operations = [
        migrations.CreateModel(
            name="GuiaEmissao",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("numero", models.CharField(db_index=True, max_length=100, unique=True)),
                ("caminho_guia", models.TextField()),
                ("pasta_documentos", models.TextField()),
                ("data_emissao", models.DateTimeField(blank=True, db_index=True, null=True)),
                ("remetente", models.CharField(max_length=180)),
                ("email_remetente", models.EmailField(blank=True, max_length=254)),
                ("criado_em", models.DateTimeField(auto_now_add=True)),
                ("atualizado_em", models.DateTimeField(auto_now=True)),
                ("processada_por", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name="guias_emissao_processadas", to=settings.AUTH_USER_MODEL)),
            ],
            options={
                "verbose_name": "Guia de emissão",
                "verbose_name_plural": "Guias de emissão",
                "ordering": ["-data_emissao", "-criado_em"],
            },
        ),
        migrations.CreateModel(
            name="DistribuicaoCopia",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("documento", models.CharField(db_index=True, max_length=255)),
                ("documento_normalizado", models.CharField(db_index=True, max_length=255)),
                ("revisao", models.CharField(blank=True, db_index=True, max_length=40)),
                ("arquivo_origem", models.TextField()),
                ("destinatario", models.CharField(db_index=True, max_length=180)),
                ("email_destinatario", models.EmailField(blank=True, max_length=254)),
                ("caminho_copia", models.TextField()),
                ("status", models.CharField(choices=[("EMITIDA", "Em poder do recebedor"), ("RECOLHIMENTO_PENDENTE", "Recolhimento pendente"), ("RECOLHIDA", "Recolhida"), ("SUBSTITUIDA", "Substituída"), ("CANCELADA", "Cancelada"), ("EXTRAVIADA", "Extraviada/justificada")], db_index=True, default="EMITIDA", max_length=40)),
                ("emitida_em", models.DateTimeField(db_index=True)),
                ("recolhida_em", models.DateTimeField(blank=True, null=True)),
                ("observacao", models.TextField(blank=True)),
                ("criado_em", models.DateTimeField(auto_now_add=True)),
                ("atualizado_em", models.DateTimeField(auto_now=True)),
                ("guia", models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name="distribuicoes", to="carimbos.guiaemissao")),
                ("recolhida_por", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name="copias_controladas_recolhidas", to=settings.AUTH_USER_MODEL)),
            ],
            options={
                "verbose_name": "Distribuição de cópia",
                "verbose_name_plural": "Distribuições de cópias",
                "ordering": ["-emitida_em", "documento", "destinatario"],
            },
        ),
        migrations.AddConstraint(
            model_name="distribuicaocopia",
            constraint=models.UniqueConstraint(fields=("guia", "documento_normalizado", "revisao", "destinatario"), name="uniq_distribuicao_guia_doc_rev_dest"),
        ),
        migrations.AddIndex(
            model_name="distribuicaocopia",
            index=models.Index(fields=["documento_normalizado", "revisao", "status"], name="carimbos_di_documen_54a711_idx"),
        ),
        migrations.AddIndex(
            model_name="distribuicaocopia",
            index=models.Index(fields=["destinatario", "status"], name="carimbos_di_destina_cc2937_idx"),
        ),
    ]
