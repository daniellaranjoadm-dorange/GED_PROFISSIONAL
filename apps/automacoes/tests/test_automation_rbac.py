from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse

from .rbac_helpers import grant_rbac


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
