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
        self.assertContains(response, "Status PCF")
        self.assertContains(response, "Responsável")

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
