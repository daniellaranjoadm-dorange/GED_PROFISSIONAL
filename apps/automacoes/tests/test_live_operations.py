from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse

from apps.automacoes.services.live_operations import LiveOperationsService


class LiveOperationsServiceTests(TestCase):
    def test_build_payload_returns_expected_sections(self):
        payload = LiveOperationsService.build_payload()

        self.assertIn("ops", payload)
        self.assertIn("runtime_events", payload)
        self.assertIn("runtime_metrics_dashboard", payload)
        self.assertIn("runtime_trends", payload)
        self.assertIn("predictive_runtime", payload)
        self.assertIn("live", payload)


class LiveOperationsViewTests(TestCase):
    def setUp(self):
        User = get_user_model()
        self.user = User.objects.create_user(
            username="live_ops_user",
            password="testpass123",
        )

    def test_live_operations_partial_requires_login(self):
        response = self.client.get(reverse("automacoes:ops_center_live_partial"))
        self.assertIn(response.status_code, [301, 302])

    def test_live_operations_partial_authenticated_returns_200(self):
        self.client.login(username="live_ops_user", password="testpass123")

        response = self.client.get(reverse("automacoes:ops_center_live_partial"))

        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, "automacoes/partials/_ops_live_operations.html")
