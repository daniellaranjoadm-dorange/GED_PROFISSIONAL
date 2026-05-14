from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse

from apps.automacoes.services.runtime_health_api import RuntimeHealthAPIService


class RuntimeHealthAPIServiceTests(TestCase):
    def test_health_payload_is_json_safe(self):
        payload = RuntimeHealthAPIService.health()

        self.assertIn("status", payload)
        self.assertIn("score", payload)
        self.assertIn("risk", payload)
        self.assertIn("generated_at", payload)


class RuntimeHealthAPIViewTests(TestCase):
    def setUp(self):
        User = get_user_model()
        self.user = User.objects.create_user(
            username="runtime_api_user",
            password="testpass123",
        )

    def test_runtime_health_api_requires_login(self):
        response = self.client.get(reverse("automacoes:runtime_health_api"))
        self.assertIn(response.status_code, [301, 302])

    def test_runtime_health_api_authenticated_returns_json(self):
        self.client.login(username="runtime_api_user", password="testpass123")

        response = self.client.get(reverse("automacoes:runtime_health_api"))

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response["Content-Type"], "application/json")
        self.assertIn("status", response.json())
