from django.test import SimpleTestCase

from apps.automacoes.services.dashboard_engine import (
    montar_automacoes_dashboard,
)


class DashboardEngineTests(SimpleTestCase):
    def test_monta_cards_principais_com_metricas(self):
        kpis = {
            "total_ld": 10,
            "total_ld_com_pcf": 7,
            "total_ld_sem_pcf": 3,
            "total_pcfs": 5,
            "total_pcfs_open": 2,
            "total_pcfs_not_released": 1,
            "total_transmittals": 8,
            "total_transmittals_unicos": 4,
            "total_transmittals_sem_pdf": 1,
            "total_km_index": 100,
            "total_km_docs_index": 80,
            "total_km_transmittals_index": 20,
        }

        automacoes = montar_automacoes_dashboard(kpis)

        self.assertEqual(len(automacoes), 5)
        self.assertEqual(automacoes[0]["nome"], "Atualização LD")
        self.assertEqual(automacoes[0]["metricas"][0]["valor"], 10)
        self.assertEqual(automacoes[1]["metricas"][2]["valor"], 1)
        self.assertEqual(automacoes[3]["metricas"][1]["valor"], 80)

    def test_injeta_health_por_nome_da_rotina(self):
        kpis = {}
        health_map = {
            "Atualização LD": {
                "estado": "ONLINE",
                "classe": "auto-status-online",
            }
        }

        automacoes = montar_automacoes_dashboard(kpis, health_map=health_map)

        self.assertEqual(automacoes[0]["health"]["estado"], "ONLINE")
        self.assertEqual(automacoes[1]["health"], {})

    def test_usa_zero_como_fallback_para_kpi_ausente(self):
        automacoes = montar_automacoes_dashboard({})

        self.assertEqual(automacoes[0]["metricas"][0]["valor"], 0)
        self.assertEqual(automacoes[1]["metricas"][0]["valor"], 0)
        self.assertEqual(automacoes[2]["metricas"][0]["valor"], 0)
