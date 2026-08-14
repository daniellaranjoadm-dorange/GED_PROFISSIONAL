from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse

from apps.automacoes.models import DocumentoLD
from apps.automacoes.tests.rbac_helpers import grant_rbac
from apps.documentos.models import Documento, DocumentoReferenciaExterna


class DocumentCenterViewTests(TestCase):
    def setUp(self):
        User = get_user_model()
        self.user = User.objects.create_user(username="central_docs", password="testpass123")
        grant_rbac(self.user, "automacoes.visualizar")
        self.client.force_login(self.user)

        self.documento = Documento.objects.create(
            codigo="DOC-DOX-001",
            revisao="A",
            titulo="Documento integrado",
            disciplina="Mecânica",
        )
        DocumentoLD.objects.create(
            origem_aba="LD PROJETO BASICO",
            documento="TP-001",
            revisao="A",
            documento_ged=self.documento,
            numero_interno="DOX-7788",
            numero_documento_km="805-100",
            transmittal_km="T-45976",
            pcf="PCF-001",
            grd="GRD-001",
            disciplina="Mecânica",
            status_documento="Aprovado com comentários",
            status_grd="Emitido",
            status_final_pcf="RELEASED WITH COMMENTS",
            resp_for_issue="Kongsberg",
            casco="CMN-01",
            medicao_emissao="01/05/2026",
            medicao_aprovacao="01/06/2026",
        )
        DocumentoReferenciaExterna.objects.create(
            documento=self.documento,
            sistema=DocumentoReferenciaExterna.SISTEMA_DOX,
            identificador_externo="DOX-7788",
            url="https://dox.example/document/7788",
        )

    def test_exibe_documento_e_relacionamentos_integrados(self):
        response = self.client.get(reverse("automacoes:central_documentos"))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Central de Documentos")
        self.assertContains(response, reverse("automacoes:central_documentos"))
        self.assertContains(response, "DOC-DOX-001")
        self.assertContains(response, "805-100")
        self.assertContains(response, "T-45976")
        self.assertContains(response, "PCF-001")
        self.assertContains(response, "DOX-7788")

    def test_filtro_sem_ld_remove_documento_vinculado(self):
        response = self.client.get(
            reverse("automacoes:central_documentos"), {"vinculo": "sem_ld"}
        )
        self.assertNotContains(response, "DOC-DOX-001")

    def test_exibe_e_aplica_filtros_gerenciais_da_ld(self):
        response = self.client.get(
            reverse("automacoes:central_documentos"),
            {
                "status": "Aprovado com comentários",
                "emissao": "Emitido",
                "status_pcf": "RELEASED WITH COMMENTS",
                "responsavel": "Kongsberg",
                "casco": "CMN-01",
                "origem": "LD PROJETO BASICO",
            },
        )
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "DOC-DOX-001")
        self.assertContains(response, "Status geral")
        self.assertContains(response, "Status da PCF")
        self.assertContains(response, "Responsável")
        self.assertContains(response, "Filtros ativos")
        self.assertContains(response, "Excel filtrado")
        self.assertContains(response, "PPTX executivo")
        self.assertContains(response, "Salvar PDF")
        self.assertContains(response, "status_doc=Aprovado+com+coment%C3%A1rios")
        self.assertContains(response, "status_grd=Emitido")
        self.assertContains(response, "responsavel=Kongsberg")
        self.assertContains(response, "casco=CMN-01")

    def test_filtro_gerencial_sem_correspondencia_remove_documento(self):
        response = self.client.get(
            reverse("automacoes:central_documentos"), {"casco": "CMN-99"}
        )
        self.assertNotContains(response, "DOC-DOX-001")
        self.assertContains(response, "Documentos no escopo")
        self.assertContains(response, "<strong>0</strong>", html=True)

    def test_cards_refletem_o_recorte_filtrado(self):
        response = self.client.get(
            reverse("automacoes:central_documentos"), {"casco": "CMN-01"}
        )
        self.assertContains(response, "Progresso de emissão")
        self.assertContains(response, "100,0%")
        self.assertContains(response, "Comentários open")

    def test_requer_autenticacao(self):
        self.client.logout()
        response = self.client.get(reverse("automacoes:central_documentos"))
        self.assertEqual(response.status_code, 302)

    def test_filtros_de_medicao_reaparecem_e_filtram_a_ld(self):
        response = self.client.get(
            reverse("automacoes:central_documentos"),
            {"medicao_emissao": "01/05/2026", "medicao_aprovacao": "01/06/2026"},
        )
        self.assertContains(response, "Medição da emissão")
        self.assertContains(response, "Medição da aprovação")
        self.assertContains(response, "DOC-DOX-001")

    def test_indicadores_nao_confundem_nao_recebido_nem_sem_comentarios(self):
        aprovado = Documento.objects.create(codigo="DOC-APROV-001", revisao="0")
        nao_recebido = Documento.objects.create(codigo="DOC-PEND-001", revisao="0")
        DocumentoLD.objects.create(
            origem_aba="LD Projeto Basico", documento="TP-APROV", revisao="0",
            documento_ged=aprovado, status_documento="Aprovado sem Comentários",
            status_grd="Emitido",
        )
        DocumentoLD.objects.create(
            origem_aba="LD Projeto Basico", documento="TP-PEND", revisao="0",
            documento_ged=nao_recebido, status_documento="Não Recebido",
            status_grd="Não Emitido",
        )
        response = self.client.get(reverse("automacoes:central_documentos"))
        self.assertEqual(response.context["metricas"]["aprovados_sem_comentarios"], 1)
        self.assertEqual(response.context["metricas"]["recebidos_pendentes"], 0)

        response = self.client.get(
            reverse("automacoes:central_documentos"),
            {"indicador": "aprovados_sem_comentarios"},
        )
        self.assertContains(response, "DOC-APROV-001")
        self.assertNotContains(response, "DOC-PEND-001")
