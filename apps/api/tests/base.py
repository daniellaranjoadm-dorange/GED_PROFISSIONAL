from django.contrib.auth import get_user_model
from django.test import TestCase
from django.utils import timezone

from apps.contas.models import Role, RolePermission, UserRole
from apps.documentos.models import Documento, DocumentoMestre, Projeto


class ApiTestCase(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.user = get_user_model().objects.create_user(username="api-reader")
        role = Role.objects.create(nome="API_TEST_READER")
        RolePermission.objects.create(role=role, codigo="ged.visualizar")
        UserRole.objects.create(user=cls.user, role=role)
        cls.project = Projeto.objects.create(nome="First", pasta_base="private-path")
        cls.empty_project = Projeto.objects.create(nome="Empty", pasta_base="private-path", ativo=False)
        cls.master = DocumentoMestre.objects.create(codigo="DOC", codigo_normalizado="DOC")
        cls.old = Documento.objects.create(
            codigo="DOC", titulo="Old", revisao="0", mestre=cls.master, projeto=cls.project,
            disciplina="Hull", tipo_doc="Drawing", status_documento="Received",
        )
        cls.current = Documento.objects.create(codigo="DOC", titulo="Current", revisao="1", mestre=cls.master)
        cls.master.revisao_atual = cls.current
        cls.master.save(update_fields=["revisao_atual"])
        cls.inactive = Documento.objects.create(codigo="INACTIVE", titulo="Hidden", ativo=False)
        cls.deleted = Documento.objects.create(codigo="DELETED", titulo="Hidden", deletado_em=timezone.now())

    def setUp(self):
        self.client.force_login(self.user)

    def assert_error(self, response, status, code):
        self.assertEqual(response.status_code, status)
        self.assertEqual(response["Content-Type"], "application/json")
        self.assertEqual(set(response.json()), {"error"})
        self.assertEqual(set(response.json()["error"]), {"code", "message"})
        self.assertEqual(response.json()["error"]["code"], code)
        self.assertNotIn("Location", response)
