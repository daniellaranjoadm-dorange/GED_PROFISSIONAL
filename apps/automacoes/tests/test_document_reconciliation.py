from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse

from apps.automacoes.models import DocumentoLD
from apps.automacoes.tests.rbac_helpers import grant_rbac
from apps.documentos.models import Documento


class DocumentReconciliationTests(TestCase):
    def setUp(self):
        User = get_user_model()
        self.user = User.objects.create_user(username="reconciliador", password="testpass123")
        grant_rbac(self.user, "automacoes.visualizar")
        self.client.force_login(self.user)
        self.candidato = Documento.objects.create(
            codigo="DOC-001", revisao="B", titulo="Versão existente"
        )
        self.pendente = DocumentoLD.objects.create(
            origem_aba="LD PROJETO BASICO",
            documento="DOC 001",
            revisao="A",
            titulo="Revisão recebida",
        )

    def test_exibe_sugestao_sem_persistir_vinculo(self):
        response = self.client.get(reverse("automacoes:reconciliacao_documentos"))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "DOC 001")
        self.assertContains(response, "revisão divergente")
        self.pendente.refresh_from_db()
        self.assertIsNone(self.pendente.documento_ged)

    def test_remove_da_fila_quando_ja_vinculado(self):
        self.pendente.documento_ged = self.candidato
        self.pendente.save(update_fields=["documento_ged"])
        response = self.client.get(reverse("automacoes:reconciliacao_documentos"))
        self.assertNotContains(response, "DOC 001")
