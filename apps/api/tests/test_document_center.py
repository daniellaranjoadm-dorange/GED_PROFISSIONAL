from django.contrib.auth import get_user_model

from apps.contas.models import Role, RolePermission, UserRole

from .base import ApiTestCase


class DocumentCenterPermissionTests(ApiTestCase):
    def endpoints(self):
        return (
            "/api/v1/document-center/",
            "/api/v1/document-center/metrics/",
            "/api/v1/document-center/filters/",
        )

    def grant_automation_permission(self, user):
        role = Role.objects.create(
            nome=f"AUTOMACOES_API_{user.pk}"
        )
        RolePermission.objects.create(
            role=role,
            codigo="automacoes.visualizar",
        )
        UserRole.objects.create(
            user=user,
            role=role,
        )

    def test_anonymous(self):
        self.client.logout()

        for endpoint in self.endpoints():
            self.assert_error(
                self.client.get(endpoint),
                401,
                "authentication_required",
            )

    def test_without_automation_permission(self):
        for endpoint in self.endpoints():
            self.assert_error(
                self.client.get(endpoint),
                403,
                "permission_denied",
            )

    def test_authorized(self):
        self.grant_automation_permission(self.user)

        for endpoint in self.endpoints():
            response = self.client.get(endpoint)
            self.assertEqual(response.status_code, 200)

    def test_post_is_not_allowed(self):
        self.grant_automation_permission(self.user)

        for endpoint in self.endpoints():
            response = self.client.post(endpoint)

            self.assert_error(
                response,
                405,
                "method_not_allowed",
            )
            self.assertEqual(response["Allow"], "GET")

    def test_authorized_user_does_not_need_ged_permission(self):
        user = get_user_model().objects.create_user(
            username="automation-only"
        )
        self.grant_automation_permission(user)
        self.client.force_login(user)

        for endpoint in self.endpoints():
            self.assertEqual(
                self.client.get(endpoint).status_code,
                200,
            )

from apps.automacoes.models import DocumentoLD
from apps.documentos.models import DocumentoReferenciaExterna


class DocumentCenterContractTests(ApiTestCase):
    @classmethod
    def setUpTestData(cls):
        super().setUpTestData()

        role = Role.objects.create(nome="DOCUMENT_CENTER_CONTRACT")
        RolePermission.objects.create(
            role=role,
            codigo="automacoes.visualizar",
        )
        UserRole.objects.create(
            user=cls.user,
            role=role,
        )

        cls.ld = DocumentoLD.objects.create(
            origem_aba="LD TESTE API",
            documento_ged=cls.current,
            documento="DOC",
            revisao="1",
            titulo="Current",
            disciplina="Hull",
            status_documento="Para Construção",
            status_grd="Emitido",
            grd="GRD-TEST-001",
            data_grd="14/09/2026",
            pcf="PCF-TEST-001",
            data_pcf="14/09/2026",
            status_final_pcf="RELEASED",
            resp_for_issue="API Tester",
            numero_interno="INT-TEST-001",
            casco="CMN-01",
            qtd_comentarios="2",
            open_comments="1",
            medicao_emissao="14/09/2026",
            medicao_aprovacao="",
            cronograma_inicio="01/09/2026",
            cronograma_termino="30/09/2026",
            numero_documento_km="KM-TEST-001",
            transmittal_km="TR-KM-001",
            data_recebimento_km="13/09/2026",
            arquivo_km_encontrado=True,
            status_vinculo_km=DocumentoLD.STATUS_VINCULO_KM_AUTO,
            score_vinculo_km=100,
            revisao_km="1",
            status_revisao_km=DocumentoLD.STATUS_REVISAO_KM_OK,
        )

        cls.dox = DocumentoReferenciaExterna.objects.create(
            documento=cls.current,
            sistema="DOX",
            identificador_externo="DOX-TEST-001",
            url="",
            status_externo="SYNC",
            divergente=False,
        )

    def test_list_contract_and_null_project(self):
        response = self.client.get(
            "/api/v1/document-center/?page=1&page_size=200"
        )

        self.assertEqual(response.status_code, 200)

        data = response.json()
        self.assertEqual(data["count"], 2)
        self.assertEqual(data["page"], 1)
        self.assertEqual(data["page_size"], 200)
        self.assertEqual(data["total_pages"], 1)

        document = next(
            item
            for item in data["results"]
            if item["id"] == self.current.pk
        )

        self.assertEqual(document["document_number"], "DOC")
        self.assertEqual(document["revision"], "1")
        self.assertTrue(document["is_current_revision"])

        # A API deve preservar a realidade do banco.
        # Nenhum projeto HANDY/GLP/MR1 pode ser fabricado.
        self.assertIsNone(document["project"])

    def test_ld_is_serialized(self):
        response = self.client.get(
            "/api/v1/document-center/?q=DOC&page_size=200"
        )
        self.assertEqual(response.status_code, 200)

        document = next(
            item
            for item in response.json()["results"]
            if item["id"] == self.current.pk
        )

        self.assertEqual(len(document["ld_records"]), 1)

        ld = document["ld_records"][0]
        self.assertEqual(ld["source"], "LD TESTE API")
        self.assertEqual(ld["grd"], "GRD-TEST-001")
        self.assertEqual(ld["pcf"], "PCF-TEST-001")
        self.assertEqual(ld["hull"], "CMN-01")
        self.assertEqual(ld["km_document_number"], "KM-TEST-001")
        self.assertEqual(ld["km_transmittal"], "TR-KM-001")
        self.assertTrue(ld["km_file_found"])
        self.assertEqual(ld["km_link_status"], "AUTO")
        self.assertEqual(ld["km_link_score"], 100)
        self.assertEqual(ld["km_revision_status"], "OK")

    def test_external_reference_is_serialized(self):
        response = self.client.get(
            "/api/v1/document-center/?q=DOC&page_size=200"
        )
        self.assertEqual(response.status_code, 200)

        document = next(
            item
            for item in response.json()["results"]
            if item["id"] == self.current.pk
        )

        self.assertEqual(len(document["external_references"]), 1)

        reference = document["external_references"][0]
        self.assertEqual(reference["system"], "DOX")
        self.assertEqual(
            reference["external_identifier"],
            "DOX-TEST-001",
        )
        self.assertEqual(reference["external_status"], "SYNC")
        self.assertFalse(reference["divergent"])

    def test_page_size_is_limited_to_200(self):
        response = self.client.get(
            "/api/v1/document-center/?page_size=999"
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["page_size"], 200)

    def test_search_filter_is_applied(self):
        response = self.client.get(
            "/api/v1/document-center/?q=INT-TEST-001"
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["count"], 1)
        self.assertEqual(
            response.json()["results"][0]["id"],
            self.current.pk,
        )

    def test_filters_are_service_backed(self):
        response = self.client.get(
            "/api/v1/document-center/filters/"
        )

        self.assertEqual(response.status_code, 200)

        data = response.json()
        self.assertIn("Hull", data["disciplinas"])
        self.assertIn("Para Construção", data["status"])
        self.assertIn("Emitido", data["emissoes"])
        self.assertIn("RELEASED", data["status_pcf"])
        self.assertIn("API Tester", data["responsaveis"])
        self.assertIn("CMN-01", data["cascos"])
        self.assertIn("LD TESTE API", data["origens"])

    def test_metrics_follow_type_filter(self):
        response = self.client.get(
            "/api/v1/document-center/metrics/?tipo=Drawing"
        )

        self.assertEqual(response.status_code, 200)

        data = response.json()
        self.assertIn("total", data)
        self.assertIn("com_ld", data)
        self.assertIn("sem_ld", data)
        self.assertIn("emitidos", data)
        self.assertIn("progresso_emissao", data)

    def test_unknown_parameter_is_rejected(self):
        response = self.client.get(
            "/api/v1/document-center/?nao_existe=1"
        )

        self.assert_error(
            response,
            400,
            "invalid_query",
        )

    def test_invalid_page_size_is_rejected(self):
        response = self.client.get(
            "/api/v1/document-center/?page_size=abc"
        )

        self.assert_error(
            response,
            400,
            "invalid_query",
        )
