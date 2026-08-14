from datetime import timedelta

from django.test import TestCase
from django.utils import timezone

from apps.automacoes.models import DocumentoLD, ExecutiveMetricSnapshot
from apps.automacoes.services.executive_governance import (
    capturar_snapshot_executivo,
    qualidade_dados_executiva,
    tendencia_executiva,
)
from apps.documentos.models import Documento


class ExecutiveGovernanceTests(TestCase):
    def setUp(self):
        documento = Documento.objects.create(codigo="I-DE-001", revisao="0", titulo="Teste")
        self.ld = DocumentoLD.objects.create(
            origem_aba="LD Projeto Basico", documento="I-DE-001", revisao="0",
            documento_ged=documento, resp_for_issue="Kongsberg",
            cronograma_termino="20/08/2026", status_grd="Emitido",
        )

    def test_qualidade_expoe_score_dimensoes_e_lacunas(self):
        qualidade = qualidade_dados_executiva(DocumentoLD.objects.all())
        self.assertIn("score", qualidade)
        self.assertEqual(len(qualidade["dimensoes"]), 7)
        vinculo = next(item for item in qualidade["dimensoes"] if item["chave"] == "vinculo_ged")
        self.assertEqual(vinculo["valor"], 100.0)

    def test_snapshot_diario_e_idempotente_e_tendencia_compara_dias(self):
        atual = capturar_snapshot_executivo("LD Projeto Basico")
        repetido = capturar_snapshot_executivo("LD Projeto Basico")
        self.assertEqual(atual.id, repetido.id)

        anterior = ExecutiveMetricSnapshot.objects.create(
            origem="LD Projeto Basico",
            data_referencia=timezone.localdate() - timedelta(days=7),
            total=1, emitidos=0, progresso=0, vencidos_nao_emitidos=1,
        )
        tendencia = tendencia_executiva(["LD Projeto Basico"])
        self.assertTrue(tendencia["historico_suficiente"])
        self.assertEqual(tendencia["anterior"].id, anterior.id)
        self.assertEqual(tendencia["delta_progresso"], 100.0)

    def test_tendencia_multiplas_origens_e_agregada_sem_escolher_uma_ld(self):
        hoje = timezone.localdate()
        anterior = hoje - timedelta(days=1)
        ExecutiveMetricSnapshot.objects.create(origem="A", data_referencia=anterior, total=100, emitidos=10, progresso=10)
        ExecutiveMetricSnapshot.objects.create(origem="B", data_referencia=anterior, total=100, emitidos=30, progresso=30)
        ExecutiveMetricSnapshot.objects.create(origem="A", data_referencia=hoje, total=100, emitidos=20, progresso=20)
        ExecutiveMetricSnapshot.objects.create(origem="B", data_referencia=hoje, total=100, emitidos=40, progresso=40)
        tendencia = tendencia_executiva(["A", "B"])
        self.assertEqual(tendencia["delta_progresso"], 10.0)
