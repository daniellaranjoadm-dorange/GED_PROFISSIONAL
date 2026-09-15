from contextlib import ExitStack
from unittest.mock import PropertyMock, patch

from django.contrib.auth import get_user_model
from django.db import connection
from django.db.models.fields.files import FieldFile
from django.test import Client
from django.test.utils import CaptureQueriesContext
from django.urls import reverse
from django.utils import timezone

from apps.automacoes.models import DocumentoLD, PCFTimeline, PendenciaDocumental, TransmittalKM
from apps.automacoes.services.document_360 import consultar_documento_360
from apps.api.document_360_serializers import serialize_document_360
from apps.contas.models import Role, RolePermission, UserRole
from apps.documentos.models import (
    ArquivoDocumento, Documento, DocumentoAprovacao, DocumentoMestre,
    DocumentoReferenciaExterna, DocumentoVersao, DocumentoWorkflowHistorico,
    DocumentoWorkflowStatus, LogAuditoria, WorkflowEtapa,
)
from .base import ApiTestCase


class Document360Tests(ApiTestCase):
    @classmethod
    def setUpTestData(cls):
        super().setUpTestData()
        role = Role.objects.create(nome="DOCUMENT_360_READER")
        RolePermission.objects.create(role=role, codigo="automacoes.visualizar")
        UserRole.objects.create(user=cls.user, role=role)
        cls.stage = WorkflowEtapa.objects.create(codigo="DOC_CONTROL", nome="Control", ordem=4)
        cls.current.etapa = cls.stage
        cls.current.etapa_atual = "LEGACY_DIFFERENT"
        cls.current.save(update_fields=["etapa", "etapa_atual"])
        for doc in (cls.inactive, cls.deleted):
            doc.mestre = cls.master
            doc.save(update_fields=["mestre"])
        cls.ld = DocumentoLD.objects.create(
            documento_ged=cls.current, documento="LD-DIFFERENT", revisao="Z",
            origem_aba="A", disciplina="LD discipline", status_documento="LD status",
            caminho_documento="C:/PRIVATE/document.pdf", caminho_grd="C:/PRIVATE/grd.pdf",
            caminho_pcf="C:/PRIVATE/pcf.xlsx", caminho_resposta="C:/PRIVATE/response.xlsx",
            caminho_grd_resposta="C:/PRIVATE/response-grd.pdf",
        )
        cls.ld_second = DocumentoLD.objects.create(
            documento_ged=cls.current, documento="LD-SECOND", origem_aba="B", revisao="2",
        )
        cls.reference = DocumentoReferenciaExterna.objects.create(
            documento=cls.current, sistema="DOX", identificador_externo="DOX-1",
            url="file:///PRIVATE/reference", metadados={"path": "C:/PRIVATE/key", "token": "PRIVATE_SECRET"},
            divergencias=[{"path": "C:/PRIVATE/divergence"}], divergente=True,
        )
        cls.pcf = PCFTimeline.objects.create(
            documento_ged=cls.current, numero_pcf="PCF-1", numero_documento="PCF-DIFFERENT",
            revisao_pcf="B", status_final="RELEASED", data_recebimento="15/09/2026",
            caminho="C:/PRIVATE/pcf.xlsx", pcf_link="file:///PRIVATE/pcf-link",
        )
        cls.transmittal = TransmittalKM.objects.create(
            documento_ged=cls.current, documento="KM-DIFFERENT", transmittal_numero="TR-1",
            arquivo_pdf="C:/PRIVATE/transmittal.pdf", pasta="C:/PRIVATE/folder",
            observacao_parse="PRIVATE_SECRET",
        )
        cls.state = DocumentoWorkflowStatus.objects.create(documento=cls.current, etapa=cls.stage)
        cls.history = DocumentoWorkflowHistorico.objects.create(
            documento=cls.current, etapa=cls.stage, usuario=cls.user,
            acao="AJUSTE_MANUAL", data=timezone.now(), observacao="C:/PRIVATE/workflow",
        )
        cls.approval = DocumentoAprovacao.objects.create(
            documento=cls.current, etapa=cls.stage, usuario=cls.user,
            status="aprovado", comentario="PRIVATE_SECRET",
        )
        cls.file = ArquivoDocumento.objects.create(
            documento=cls.current, arquivo="documentos/anexos/PRIVATE/file.pdf",
            nome_original="C:/PRIVATE/file.pdf", tipo="PDF",
        )
        cls.version = DocumentoVersao.objects.create(
            documento=cls.current, numero_revisao="FILE-99",
            arquivo="documentos/versoes/PRIVATE/version.pdf", criado_por=cls.user,
            observacao="PRIVATE_SECRET",
        )
        cls.pending = PendenciaDocumental.objects.create(
            documento=cls.current, registro_ld=cls.ld, chave="private-key",
            tipo="PCF_NAO_LIBERADA", titulo="Review PCF", responsavel=cls.user,
            descricao="C:/PRIVATE/pending", acao_recomendada="PRIVATE_SECRET",
            metadados={"path": "C:/PRIVATE/pending", "token": "PRIVATE_SECRET"},
        )
        cls.log = LogAuditoria.objects.create(
            documento=cls.current, usuario=cls.user, acao="Consulta anterior",
            descricao="C:/PRIVATE/audit PRIVATE_SECRET",
        )

    def endpoint(self, pk=None):
        return reverse("api:document-center-detail", kwargs={"document_id": pk or self.current.pk})

    def data(self):
        response = self.client.get(self.endpoint())
        self.assertEqual(response.status_code, 200)
        return response.json()

    def test_anonymous_401(self):
        self.client.logout()
        self.assert_error(self.client.get(self.endpoint()), 401, "authentication_required")

    def test_ged_permission_is_insufficient(self):
        denied = get_user_model().objects.create_user(username="core-only-360")
        role = Role.objects.create(nome="CORE_ONLY_360")
        RolePermission.objects.create(role=role, codigo="ged.visualizar")
        UserRole.objects.create(user=denied, role=role)
        self.client.force_login(denied)
        self.assert_error(self.client.get(self.endpoint()), 403, "permission_denied")

    def test_automation_only_permission_succeeds(self):
        allowed = get_user_model().objects.create_user(username="automation-only-360")
        UserRole.objects.create(user=allowed, role=Role.objects.get(nome="DOCUMENT_360_READER"))
        self.client.force_login(allowed)
        self.assertEqual(self.client.get(self.endpoint()).status_code, 200)

    def test_write_methods_and_headers(self):
        for method in ("post", "put", "patch", "delete", "options", "head"):
            with self.subTest(method=method):
                response = getattr(self.client, method)(self.endpoint())
                self.assertEqual(response.status_code, 405)
                self.assertEqual(response["Allow"], "GET")
                self.assertEqual(response["Cache-Control"], "private, no-store")
                if method != "head":
                    self.assert_error(response, 405, "method_not_allowed")
        self.assertEqual(self.client.get(self.endpoint())["Cache-Control"], "private, no-store")

    def test_missing_inactive_and_deleted_404(self):
        for pk in (999999, self.inactive.pk, self.deleted.pk):
            self.assert_error(self.client.get(self.endpoint(pk)), 404, "not_found")

    def test_unknown_parameters_rejected(self):
        self.assert_error(self.client.get(self.endpoint(), {"project": "HANDY"}), 400, "invalid_query")

    def test_null_project_and_top_level_contract(self):
        data = self.data()
        self.assertIsNone(data["document"]["project"])
        self.assertEqual(set(data), {
            "document", "ld_records", "revisions", "pcf_timeline", "transmittals",
            "external_references", "workflow", "approvals", "files", "versions",
            "pending_actions", "audit_trail",
        })

    def test_all_ld_records_and_divergences_preserved(self):
        data = self.data()
        self.assertEqual([r["id"] for r in data["ld_records"]], [self.ld.pk, self.ld_second.pk])
        self.assertEqual(data["ld_records"][0]["revision"], "Z")
        self.assertEqual(data["ld_records"][0]["discipline"], "LD discipline")
        self.assertEqual(data["document"]["revision"], "1")
        self.assertIsNone(data["document"]["discipline"])

    def test_pcf_transmittal_and_references(self):
        data = self.data()
        self.assertEqual(data["pcf_timeline"][0]["id"], self.pcf.pk)
        self.assertEqual(data["pcf_timeline"][0]["received_date"], "15/09/2026")
        self.assertEqual(data["transmittals"][0]["id"], self.transmittal.pk)
        reference = data["external_references"][0]
        self.assertEqual(reference["id"], self.reference.pk)
        self.assertEqual(reference["system"], "DOX")
        self.assertEqual(reference["external_status"], "")
        self.assertTrue(reference["divergent"])

    def test_workflow_and_approvals(self):
        data = self.data()
        workflow = data["workflow"]
        self.assertEqual(workflow["current"]["id"], self.state.pk)
        self.assertIsNone(workflow["current"]["deadline"])
        self.assertEqual(workflow["document_stage"]["code"], "DOC_CONTROL")
        self.assertEqual(workflow["legacy_stage"], "LEGACY_DIFFERENT")
        self.assertEqual(workflow["history"][0]["id"], self.history.pk)
        self.assertEqual(workflow["history"][0]["user"]["id"], self.user.pk)
        self.assertEqual(data["approvals"][0]["id"], self.approval.pk)

    def test_files_versions_pending_and_audit(self):
        data = self.data()
        self.assertEqual(data["files"][0]["name"], "file.pdf")
        self.assertEqual(data["versions"][0]["name"], "version.pdf")
        self.assertEqual(data["versions"][0]["revision"], "FILE-99")
        self.assertEqual(data["versions"][0]["created_by"]["id"], self.user.pk)
        self.assertEqual(data["pending_actions"][0]["ld_record_id"], self.ld.pk)
        self.assertEqual(data["audit_trail"][0]["id"], self.log.pk)

    def test_revisions_include_history_not_file_versions(self):
        data = self.data()
        revisions = data["revisions"]
        self.assertEqual([r["id"] for r in revisions], [self.old.pk, self.current.pk, self.inactive.pk, self.deleted.pk])
        self.assertEqual([r["id"] for r in revisions if r["is_current_revision"]], [self.current.pk])
        self.assertFalse(revisions[2]["active"])
        self.assertIsNotNone(revisions[3]["deleted_at"])
        self.assertNotIn("FILE-99", [r["revision"] for r in revisions])

    def test_absent_relations_and_master(self):
        doc = Documento.objects.create(codigo="EMPTY-360", titulo="Empty")
        data = self.client.get(self.endpoint(doc.pk)).json()
        for key in ("ld_records", "revisions", "pcf_timeline", "transmittals", "external_references", "approvals", "files", "versions", "pending_actions", "audit_trail"):
            self.assertEqual(data[key], [])
        self.assertEqual(data["workflow"], {"document_stage": None, "legacy_stage": None, "current": None, "history": []})

    def test_unlinked_and_other_document_records_are_not_guessed(self):
        PCFTimeline.objects.create(numero_documento="DOC", pcf_link="unlinked")
        TransmittalKM.objects.create(documento="DOC", transmittal_numero="UNLINKED")
        DocumentoLD.objects.create(documento_ged=self.old, documento="DOC", origem_aba="OTHER")
        data = self.data()
        self.assertEqual(len(data["pcf_timeline"]), 1)
        self.assertEqual(len(data["transmittals"]), 1)
        self.assertEqual(len(data["ld_records"]), 2)

    def test_resolved_pending_actions_are_preserved(self):
        self.pending.status = "RESOLVIDA"
        self.pending.save(update_fields=["status"])
        self.assertEqual(self.data()["pending_actions"][0]["status"], "RESOLVIDA")

    def test_no_paths_secrets_or_arbitrary_json(self):
        text = self.client.get(self.endpoint()).content.decode()
        for value in ("PRIVATE", "caminho_", "arquivo_pdf", "file:///", "documentos/anexos", "documentos/versoes", "metadados", "divergencias", "private-key"):
            self.assertNotIn(value, text)
        self.assertNotIn('"url"', text)

    def test_windows_filename_and_null_actors(self):
        self.file.nome_original = r"\\server\PRIVATE\file.pdf"
        self.file.save(update_fields=["nome_original"])
        self.version.criado_por = None
        self.version.save(update_fields=["criado_por"])
        self.history.usuario = None
        self.history.etapa = None
        self.history.save(update_fields=["usuario", "etapa"])
        data = self.data()
        self.assertEqual(data["files"][0]["name"], "file.pdf")
        self.assertIsNone(data["versions"][0]["created_by"])
        self.assertIsNone(data["workflow"]["history"][0]["user"])
        self.assertIsNone(data["workflow"]["history"][0]["stage"])

    def test_storage_is_never_opened_or_resolved(self):
        with patch.object(FieldFile, "open", side_effect=AssertionError("storage access")), patch.object(FieldFile, "path", new_callable=PropertyMock, side_effect=AssertionError("path access")), patch.object(FieldFile, "url", new_callable=PropertyMock, side_effect=AssertionError("url access")):
            self.data()

    def test_get_is_select_only_and_records_unchanged(self):
        models = (Documento, DocumentoMestre, DocumentoLD, PCFTimeline, TransmittalKM,
                  DocumentoReferenciaExterna, DocumentoWorkflowStatus, DocumentoWorkflowHistorico,
                  DocumentoAprovacao, ArquivoDocumento, DocumentoVersao, PendenciaDocumental, LogAuditoria)
        def snapshot():
            return {model.__name__: list(model.objects.order_by("pk").values()) for model in models}
        before = snapshot()
        with CaptureQueriesContext(connection) as queries:
            self.data()
        for query in queries:
            self.assertTrue(query["sql"].lstrip().upper().startswith("SELECT"), query["sql"])
        self.assertEqual(before, snapshot())

    def test_no_sync_import_or_lifecycle_calls(self):
        targets = (
            "document_lifecycle.executar_ciclo_documental",
            "document_lifecycle.vincular_pcfs_revisoes",
            "document_lifecycle.vincular_transmittals_revisoes",
            "document_lifecycle.sincronizar_referencias_dox",
            "document_registry_sync.cadastrar_documentos_ausentes_da_ld",
            "document_registry_sync.sincronizar_documentos_ld_com_ged",
            "km_ld_sync_engine.executar_sync_km_ld",
            "document_link_engine.executar_vinculo_km_ld",
            "timeline_pcfs.executar",
            "transmittal_km.executar",
            "transmittal_km.processar",
        )
        with ExitStack() as stack:
            mocks = [stack.enter_context(patch("apps.automacoes.services." + target, side_effect=AssertionError(target))) for target in targets]
            self.data()
            for mock in mocks:
                mock.assert_not_called()

    def test_bounded_query_count_and_deterministic_order(self):
        with self.assertNumQueries(12):
            document = consultar_documento_360(self.current.pk)
        with self.assertNumQueries(0):
            first = serialize_document_360(document)
        for index in range(3):
            DocumentoLD.objects.create(documento_ged=self.current, documento=f"MORE-{index}", origem_aba="MORE")
        with self.assertNumQueries(12):
            document = consultar_documento_360(self.current.pk)
        with self.assertNumQueries(0):
            second = serialize_document_360(document)
        self.assertEqual(first["ld_records"], second["ld_records"][:2])
        self.assertEqual(second, self.data())

    def test_csrf_not_weakened(self):
        client = Client(enforce_csrf_checks=True)
        client.force_login(self.user)
        self.assertEqual(client.post(self.endpoint()).status_code, 403)
