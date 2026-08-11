from datetime import timedelta
from types import SimpleNamespace

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from apps.automacoes.models import ExecucaoAutomacao
from apps.automacoes.views import _classificar_saude_rotina, _km_active_filter_chips
from .rbac_helpers import grant_rbac


class OperationalStateClassificationTests(TestCase):
    def test_production_success_recent_is_operational(self):
        ultima = SimpleNamespace(
            status=ExecucaoAutomacao.STATUS_SUCESSO,
            iniciado_em=timezone.now() - timedelta(hours=2),
        )
        health = _classificar_saude_rotina(
            {"modo_operacional": "producao", "frescor_horas": 72},
            {"ultima": ultima},
        )
        self.assertEqual(health["estado"], "OPERACIONAL")
        self.assertEqual(health["card_class"], "ops-card-production")

    def test_production_success_old_is_stale(self):
        ultima = SimpleNamespace(
            status=ExecucaoAutomacao.STATUS_SUCESSO,
            iniciado_em=timezone.now() - timedelta(days=10),
        )
        health = _classificar_saude_rotina(
            {"modo_operacional": "producao", "frescor_horas": 72},
            {"ultima": ultima},
        )
        self.assertEqual(health["estado"], "DESATUALIZADO")
        self.assertEqual(health["card_class"], "ops-card-stale")

    def test_legacy_is_never_presented_as_online(self):
        ultima = SimpleNamespace(
            status=ExecucaoAutomacao.STATUS_SUCESSO,
            iniciado_em=timezone.now(),
        )
        health = _classificar_saude_rotina(
            {"modo_operacional": "legado"},
            {"ultima": ultima},
        )
        self.assertEqual(health["estado"], "LEGADO")
        self.assertEqual(health["card_class"], "ops-card-legacy")


class KMExecutiveDashboardAccessTests(TestCase):
    def setUp(self):
        self.user = get_user_model().objects.create_user(
            username="km_dashboard_user",
            password="testpass123",
        )
        grant_rbac(self.user, "automacoes.visualizar", "administracao.gerenciar")

    def test_dashboard_km_requires_login(self):
        response = self.client.get(reverse("automacoes:dashboard_km_ld"))
        self.assertEqual(response.status_code, 302)
        self.assertIn("/login/", response.url)

    def test_dashboard_km_authenticated_renders(self):
        self.client.force_login(self.user)
        response = self.client.get(reverse("automacoes:dashboard_km_ld"))
        self.assertEqual(response.status_code, 200)

    def test_filter_chips_receive_plain_lists(self):
        chips = _km_active_filter_chips({
            "busca": "",
            "phases": ["Basic"],
            "tocs": [],
            "disciplinas": [],
            "transmittals": [],
            "recebimentos": ["recebido"],
            "tps": [],
        })
        self.assertEqual(chips[0], {"label": "Phase", "valor": "Basic"})
        self.assertEqual(chips[1], {"label": "Recebimento", "valor": "Recebidos"})


class AutomationPanelGroupingTests(TestCase):
    def setUp(self):
        self.user = get_user_model().objects.create_user(
            username="automation_panel_user",
            password="testpass123",
            is_staff=True,
        )
        grant_rbac(self.user, "automacoes.visualizar", "administracao.gerenciar")

    def test_panel_separates_production_demand_and_legacy(self):
        self.client.force_login(self.user)
        response = self.client.get(reverse("automacoes:painel"))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Em produção")
        self.assertContains(response, "Sob demanda")
        self.assertContains(response, "Legado / em validação")
        self.assertContains(response, "ops-card-legacy")
        self.assertContains(response, "Ver rotinas em uso")
        self.assertContains(response, 'id="rotinas-producao"')
        self.assertContains(response, "ops-group-producao")

    def test_sidebar_exposes_module_and_item_states(self):
        self.client.force_login(self.user)
        response = self.client.get(reverse("automacoes:painel"))
        self.assertContains(response, "EM USO")
        self.assertContains(response, "EM VALIDAÇÃO")
        self.assertContains(response, "PARCIAL")
        self.assertContains(response, "RESTRITO")
        self.assertContains(response, "sidebar-item-state state-live")
        self.assertContains(response, "sidebar-item-state state-validation")
        self.assertContains(response, "sidebar-item-state state-legacy")
