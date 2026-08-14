from datetime import date, datetime, timezone
from types import SimpleNamespace

from django.contrib.auth import get_user_model
from django.test import SimpleTestCase, TestCase
from django.urls import reverse

from apps.automacoes.models import DocumentoLD
from apps.automacoes.tests.rbac_helpers import grant_rbac
from apps.automacoes.services.ld_executive_intelligence import montar_inteligencia_executiva


def registro(**valores):
    base = {
        "documento": "I-DE-001", "revisao": "0", "disciplina": "MÁQUINAS",
        "status_documento": "Não Recebido", "status_grd": "Não Emitido",
        "status_final_pcf": "", "pcf_resposta": "", "open_comments": "0",
        "cronograma_termino": "", "data_grd": "", "medicao_emissao": "",
        "medicao_aprovacao": "", "resp_for_issue": "Engenharia",
        "atualizado_em": datetime(2026, 8, 14, tzinfo=timezone.utc),
    }
    base.update(valores)
    return SimpleNamespace(**base)


class LDExecutiveIntelligenceTests(SimpleTestCase):
    def test_separa_riscos_prazos_e_pcf_sem_inflar_pendencias(self):
        itens = [
            registro(
                documento="A", status_documento="Recebido e não Emitido",
                cronograma_termino="10/08/2026", status_final_pcf="NOT RELEASED",
                open_comments="4", resp_for_issue="",
            ),
            registro(
                documento="B", status_documento="Aprovado sem Comentários",
                status_grd="Emitido", data_grd="01/08/2026",
                cronograma_termino="05/08/2026", status_final_pcf="RELEASED",
            ),
            registro(
                documento="C", status_documento="Aprovado com comentários",
                status_grd="Emitido", data_grd="12/08/2026",
                cronograma_termino="10/08/2026", status_final_pcf="RELEASED WITH COMMENTS",
            ),
        ]
        resultado = montar_inteligencia_executiva(itens, hoje=date(2026, 8, 14))

        self.assertEqual(resultado["vencidos_nao_emitidos"], 1)
        self.assertEqual(resultado["pcf_criticas"], 1)
        self.assertEqual(resultado["pcf_aguardando_resposta"], 2)
        self.assertEqual(resultado["aprovados_sem_ressalvas"], 1)
        self.assertEqual(resultado["emitidos_no_prazo"], 1)
        self.assertEqual(resultado["emitidos_atrasados"], 1)
        self.assertEqual(resultado["comentarios_abertos"], 4)
        self.assertEqual(resultado["sem_responsavel"], 1)

    def test_nao_classifica_nao_recebido_como_recebido_pendente(self):
        resultado = montar_inteligencia_executiva(
            [registro(status_documento="Não Recebido")],
            hoje=date(2026, 8, 14),
        )
        self.assertEqual(resultado["nao_recebidos"], 1)
        self.assertEqual(resultado["recebidos_pendentes"], 0)


class LDExecutiveDashboardViewTests(TestCase):
    def setUp(self):
        self.user = get_user_model().objects.create_user("direcao", password="teste")
        grant_rbac(self.user, "ld_pcf.visualizar")
        self.client.force_login(self.user)
        DocumentoLD.objects.create(
            origem_aba="LD Projeto Basico", documento="I-DE-001", revisao="0",
            disciplina="MÁQUINAS", status_documento="Recebido e não Emitido",
            status_grd="Não Emitido", status_final_pcf="NOT RELEASED",
            cronograma_termino="10/08/2026", resp_for_issue="Kongsberg",
        )

    def test_dashboard_exibe_narrativa_memoria_e_fila_de_acao(self):
        response = self.client.get(
            reverse("automacoes:dashboard_ld"), {"origem": "LD Projeto Basico"}
        )
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Leitura para decisão")
        self.assertContains(response, "Vencidos sem emissão")
        self.assertContains(response, "Documentos prioritários para ação")
        self.assertContains(response, "Medição da emissão")
        self.assertContains(response, "Responsável pela emissão")

    def test_ppt_executivo_usa_a_mesma_inteligencia(self):
        response = self.client.get(
            reverse("automacoes:dashboard_ld"),
            {"origem": "LD Projeto Basico", "export": "pptx"},
        )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(
            response["Content-Type"],
            "application/vnd.openxmlformats-officedocument.presentationml.presentation",
        )
        self.assertGreater(len(response.content), 10000)
