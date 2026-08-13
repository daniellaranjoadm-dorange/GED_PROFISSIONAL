from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse

from apps.automacoes.models import DocumentoLD
from apps.automacoes.tests.rbac_helpers import grant_rbac
from apps.documentos.models import Documento


class DocumentoDetalheLDIntegrationTests(TestCase):
    def setUp(self):
        self.user = get_user_model().objects.create_user(
            username="detalhe_ld", password="testpass123"
        )
        grant_rbac(self.user, "ged.visualizar")
        self.client.force_login(self.user)
        self.documento = Documento.objects.create(
            codigo="I-DE-4880.00-0197-100-CZ1-001",
            revisao="0",
            titulo="Fire and deck wash system",
        )

    def test_exibe_dados_e_arquivo_oficial_vinculado_sem_copiar(self):
        registro = DocumentoLD.objects.create(
            origem_aba="LD Projeto Basico",
            documento_ged=self.documento,
            documento=self.documento.codigo,
            revisao="0",
            status_documento="EMITIDO",
            status_grd="Emitido ao cliente",
            grd="GRD-123",
            data_grd="12/08/2026",
            transmittal_km="T-45976",
            numero_interno="DOX-123",
            data_recebimento_km="12/08/2026",
            caminho_documento=r"\\servidor\documentos\desenho.pdf",
        )

        response = self.client.get(
            reverse("documentos:detalhes_documento", args=[self.documento.pk])
        )

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Arquivos vinculados pelas LDs")
        self.assertContains(response, "LD Projeto Basico")
        self.assertContains(response, "GRD-123")
        self.assertContains(response, "T-45976")
        self.assertContains(response, "Emitido ao cliente")
        self.assertContains(response, "DOX-123")
        self.assertContains(response, ">DE<")
        self.assertContains(response, "desenho.pdf")
        self.assertContains(
            response,
            reverse(
                "automacoes:abrir_arquivo_ld",
                kwargs={"pk": registro.pk, "tipo": "documento"},
            ),
        )
        self.assertEqual(self.documento.arquivos.count(), 0)

    def test_mesmo_caminho_em_duas_lds_aparece_uma_vez(self):
        caminho = r"\\servidor\documentos\arquivo-unico.pdf"
        for origem in ("LD Projeto Basico", "LD Marenova Executivo"):
            DocumentoLD.objects.create(
                origem_aba=origem,
                documento_ged=self.documento,
                documento=self.documento.codigo,
                revisao="0",
                caminho_documento=caminho,
            )

        response = self.client.get(
            reverse("documentos:detalhes_documento", args=[self.documento.pk])
        )

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "arquivo-unico.pdf", count=1)
        self.assertContains(response, "LD Projeto Basico")
        self.assertContains(response, "LD Marenova Executivo")
