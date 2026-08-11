from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse

from apps.automacoes.models import DocumentoLD, ExecucaoAutomacao
from apps.contas.models import Role
from apps.solicitacoes.models import SolicitarAcesso

from .rbac_helpers import grant_rbac


class NotificationCenterTests(TestCase):
    def setUp(self):
        User = get_user_model()
        self.viewer = User.objects.create_user(username="notify_viewer", password="testpass123")
        self.admin = User.objects.create_user(username="notify_admin", password="testpass123")
        self.denied = User.objects.create_user(username="notify_denied", password="testpass123")
        grant_rbac(self.viewer, "notificacoes.visualizar")
        grant_rbac(self.admin, "notificacoes.visualizar", "administracao.gerenciar")

        ExecucaoAutomacao.objects.create(
            nome="Rotina com falha",
            status=ExecucaoAutomacao.STATUS_ERRO,
            mensagem="Falha operacional controlada",
        )
        self.role = Role.objects.create(nome="CONSULTA_NOTIFICACAO")
        SolicitarAcesso.objects.create(
            nome="Pessoa pendente",
            email="pendente@example.com",
            perfil_solicitado=self.role,
            motivo="Acesso de teste",
        )

    def test_permission_is_required(self):
        self.client.login(username="notify_denied", password="testpass123")
        response = self.client.get(reverse("automacoes:central_notificacoes"))
        self.assertIn(response.status_code, [301, 302, 403])

    def test_operational_viewer_sees_failures_but_not_access_requests(self):
        self.client.login(username="notify_viewer", password="testpass123")
        response = self.client.get(reverse("automacoes:central_notificacoes"))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Rotina com falha")
        self.assertContains(response, "Conte&uacute;do administrativo protegido", html=False)
        self.assertNotContains(response, "pendente@example.com")

    def test_admin_sees_pending_access_requests(self):
        self.client.login(username="notify_admin", password="testpass123")
        response = self.client.get(reverse("automacoes:central_notificacoes"))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "pendente@example.com")
        self.assertEqual(response.context["total_acessos_pendentes"], 1)

    @patch("apps.automacoes.services.notification_center.build_record")
    def test_overdue_pcf_is_displayed(self, build_record):
        DocumentoLD.objects.create(documento="DOC-PCF-001", pcf="PCF-001")
        build_record.return_value = {
            "situacao": "Vencida",
            "documento": "DOC-PCF-001",
            "titulo": "Documento vencido",
            "dias_atraso": 8,
            "responsavel": "Engenharia",
        }
        self.client.login(username="notify_viewer", password="testpass123")
        response = self.client.get(reverse("automacoes:central_notificacoes"))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "DOC-PCF-001")
        self.assertEqual(response.context["total_pcfs_vencidas"], 1)
