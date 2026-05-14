from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse

from apps.automacoes.services.ops_center_service import OperationsCenterService


class OperationsCenterObservabilityTests(TestCase):
    def test_dashboard_contains_observability_sections(self):
        dashboard = OperationsCenterService.build_dashboard()

        self.assertIn("telemetry", dashboard)
        self.assertIn("timeline", dashboard)
        self.assertIn("stale_count", dashboard["telemetry"])
        self.assertIsInstance(dashboard["timeline"], list)

    def test_runtime_partial_requires_login(self):
        response = self.client.get(reverse("automacoes:ops_center_runtime_partial"))

        self.assertIn(response.status_code, [301, 302])

    def test_runtime_partial_authenticated_returns_200(self):
        User = get_user_model()
        user = User.objects.create_user(
            username="ops_observer",
            password="testpass123",
        )
        self.client.login(username="ops_observer", password="testpass123")

        response = self.client.get(reverse("automacoes:ops_center_runtime_partial"))

        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(
            response,
            "automacoes/partials/_ops_runtime_observability.html",
        )
        self.assertIn("ops", response.context)
