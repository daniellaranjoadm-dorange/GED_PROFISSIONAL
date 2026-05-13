from django.test import TestCase

from apps.automacoes.models import SearchAudit
from apps.automacoes.services.search_analytics import obter_search_analytics


class SearchAnalyticsTests(TestCase):
    def test_obter_search_analytics_retorna_kpis_basicos(self):
        SearchAudit.objects.create(
            termo="MA-001",
            tipo="todos",
            total_geral=3,
            total_km=1,
            total_ld=2,
            duracao_ms=15,
        )
        SearchAudit.objects.create(
            termo="SEM-RESULTADO",
            tipo="km",
            total_geral=0,
            duracao_ms=8,
        )

        dados = obter_search_analytics(dias=30)

        self.assertEqual(dados["total_buscas"], 2)
        self.assertEqual(dados["buscas_com_resultado"], 1)
        self.assertEqual(dados["buscas_sem_resultado"], 1)
        self.assertEqual(dados["destino_totais"]["km"], 1)
        self.assertEqual(dados["destino_totais"]["ld"], 2)

    def test_obter_search_analytics_limita_periodo_invalido(self):
        dados = obter_search_analytics(dias="invalido")

        self.assertEqual(dados["periodo_dias"], 30)
        self.assertEqual(dados["total_buscas"], 0)
