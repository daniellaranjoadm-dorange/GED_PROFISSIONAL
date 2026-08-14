from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse

from apps.automacoes.models import DocumentoLD, PCFTimeline, PendenciaDocumental, TransmittalKM
from apps.automacoes.services.document_lifecycle import executar_ciclo_documental
from apps.automacoes.tests.rbac_helpers import grant_rbac
from apps.documentos.models import Documento, DocumentoMestre, DocumentoReferenciaExterna


class DocumentLifecycleTests(TestCase):
    def setUp(self):
        self.documento = Documento.objects.create(
            codigo="I-DE-4880.00-0098-000-CZ1-001",
            revisao="0",
            titulo="Arrangement lifesaving equipment",
        )
        self.ld = DocumentoLD.objects.create(
            origem_aba="LD Projeto Basico",
            documento=self.documento.codigo,
            revisao="0",
            documento_ged=self.documento,
            titulo=self.documento.titulo,
            disciplina="Segurança",
            status_documento="Recebido e não Emitido",
            status_grd="Não Emitido",
            numero_interno="DOX-0098",
            numero_documento_km="805-100",
            pcf="PCF-0098",
            status_final_pcf="NOT RELEASED",
            open_comments="3",
        )
        self.pcf = PCFTimeline.objects.create(
            tipo="PCF",
            numero_documento=self.documento.codigo,
            revisao_pcf="0",
            numero_pcf="PCF-0098",
            status_final="NOT RELEASED",
        )
        self.transmittal = TransmittalKM.objects.create(
            documento="805-100",
            transmittal_numero="T-45976",
            data_envio="12/08/2026",
        )

    def test_ciclo_integra_mestre_eventos_workflow_dox_e_pendencias(self):
        resultado = executar_ciclo_documental()

        self.documento.refresh_from_db()
        self.pcf.refresh_from_db()
        self.transmittal.refresh_from_db()
        self.assertIsNotNone(self.documento.mestre_id)
        self.assertEqual(self.documento.mestre.revisao_atual_id, self.documento.id)
        self.assertEqual(self.pcf.documento_ged_id, self.documento.id)
        self.assertEqual(self.transmittal.documento_ged_id, self.documento.id)
        self.assertEqual(self.documento.etapa_atual, "APROVACAO_CLIENTE")
        self.assertTrue(
            DocumentoReferenciaExterna.objects.filter(
                documento=self.documento,
                sistema="DOX",
                identificador_externo="DOX-0098",
            ).exists()
        )
        self.assertTrue(
            PendenciaDocumental.objects.filter(
                documento=self.documento, tipo="PCF_NAO_LIBERADA", status="ABERTA"
            ).exists()
        )
        self.assertGreater(resultado["pendencias"]["abertas"], 0)

    def test_ciclo_e_idempotente_para_mestre_e_referencias(self):
        executar_ciclo_documental()
        executar_ciclo_documental()
        self.assertEqual(DocumentoMestre.objects.count(), 1)
        self.assertEqual(DocumentoReferenciaExterna.objects.count(), 1)


class PendenciasDocumentaisViewTests(TestCase):
    def test_exibe_fila_unificada(self):
        user = get_user_model().objects.create_user("pendencias", password="teste123")
        grant_rbac(user, "automacoes.visualizar")
        documento = Documento.objects.create(codigo="DOC-PEND-001", revisao="0", titulo="Pendente")
        PendenciaDocumental.objects.create(
            chave="teste:pendencia",
            documento=documento,
            tipo="ARQUIVO_AUSENTE",
            titulo="Documento sem arquivo",
            severidade="CRITICA",
            acao_recomendada="Vincular arquivo oficial.",
        )
        self.client.force_login(user)

        response = self.client.get(reverse("automacoes:pendencias_documentais"))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Central Unificada de Pendências")
        self.assertContains(response, "DOC-PEND-001")
        self.assertContains(response, "Vincular arquivo oficial")
