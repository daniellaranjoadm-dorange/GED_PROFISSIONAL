from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.core.files.uploadedfile import SimpleUploadedFile
from django.urls import reverse

from .rbac_helpers import grant_rbac
from apps.automacoes.models import ExecucaoAutomacao


class AutomationRBACTests(TestCase):
    def setUp(self):
        User = get_user_model()
        self.viewer = User.objects.create_user(username="rbac_viewer", password="testpass123")
        self.operator = User.objects.create_user(username="rbac_operator", password="testpass123")
        grant_rbac(self.viewer, "automacoes.visualizar")
        grant_rbac(
            self.operator,
            "automacoes.visualizar",
            "automacoes.executar_ld_projeto_basico",
        )

    def test_viewer_sees_read_only_action(self):
        self.client.force_login(self.viewer)
        response = self.client.get(reverse("automacoes:painel"))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Somente consulta")

    @patch("apps.automacoes.views.atualizar_ld_projeto_basico.executar")
    def test_viewer_cannot_execute_production_routine(self, executar):
        self.client.force_login(self.viewer)
        response = self.client.post(reverse("automacoes:atualizar_ld_projeto_basico"))
        self.assertEqual(response.status_code, 302)
        executar.assert_not_called()

    @patch("apps.automacoes.views.atualizar_ld_projeto_basico.executar")
    def test_operator_can_execute_authorized_routine(self, executar):
        executar.return_value = {"ok": True, "mensagem": "OK"}
        self.client.force_login(self.operator)
        response = self.client.post(reverse("automacoes:atualizar_ld_projeto_basico"))
        self.assertEqual(response.status_code, 302)
        executar.assert_called_once()
        log = ExecucaoAutomacao.objects.get(nome="Atualização LD Projeto Básico")
        self.assertEqual(log.usuario, self.operator)
        self.assertEqual(log.origem, "painel")
        self.assertEqual(log.detalhes["metodo"], "POST")


class ConsultaLDKMRouteSecurityTests(TestCase):
    def setUp(self):
        User = get_user_model()
        self.user = User.objects.create_user(username="consulta_ld_km", password="testpass123")
        grant_rbac(
            self.user, "automacoes.visualizar", "ld_pcf.visualizar", "km.visualizar"
        )
        self.client.force_login(self.user)

    def test_consulta_le_listas_ld_e_km(self):
        self.assertEqual(self.client.get(reverse("automacoes:lista_ld")).status_code, 200)
        self.assertEqual(self.client.get(reverse("automacoes:lista_km")).status_code, 200)

    def test_consulta_nao_importa_lista_km(self):
        response = self.client.post(reverse("automacoes:importar_lista_km"), {})
        self.assertEqual(response.status_code, 302)

    def test_consulta_nao_executa_sync_km_ld(self):
        response = self.client.post(reverse("automacoes:executar_sync_km_ld"), {})
        self.assertEqual(response.status_code, 302)


class LDKMAuditTests(TestCase):
    def setUp(self):
        User = get_user_model()
        self.operator = User.objects.create_user(
            username="operador_ld_km", password="testpass123"
        )
        grant_rbac(self.operator, "automacoes.executar_sync_km_ld")
        self.client.force_login(self.operator)

    @patch("apps.automacoes.views.executar_cruzamento_ld_km")
    def test_sync_km_ld_registra_usuario_resultado_e_ip(self, executar):
        executar.return_value = {"ok": True, "mensagem": "Sincronizado", "total": 12}
        response = self.client.post(
            reverse("automacoes:executar_sync_km_ld"),
            REMOTE_ADDR="10.20.30.40",
        )
        self.assertEqual(response.status_code, 302)
        log = ExecucaoAutomacao.objects.get(nome="Sync KM ↔ LD")
        self.assertEqual(log.usuario, self.operator)
        self.assertEqual(log.ip_origem, "10.20.30.40")
        self.assertTrue(log.sucesso)

    @patch("apps.automacoes.views.importar_ld_kongsberg")
    def test_importacao_km_registra_nome_do_arquivo(self, importar):
        importar.return_value = {"ok": True, "mensagem": "Importada", "total": 3}
        arquivo = SimpleUploadedFile(
            "LD_Kongsberg_teste.xlsx",
            b"conteudo de teste",
            content_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        )
        response = self.client.post(
            reverse("automacoes:importar_lista_km"),
            {"arquivo": arquivo},
        )
        self.assertEqual(response.status_code, 302)
        log = ExecucaoAutomacao.objects.get(nome="Importar LD Kongsberg")
        self.assertEqual(log.arquivo_origem, "LD_Kongsberg_teste.xlsx")
        self.assertEqual(log.usuario, self.operator)
