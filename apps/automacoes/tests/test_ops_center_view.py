from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse


class OperationsCenterViewTests(TestCase):
    def setUp(self):
        User = get_user_model()
        self.user = User.objects.create_user(
            username="ops_user",
            password="testpass123",
        )

    def test_ops_center_requires_login(self):
        response = self.client.get(reverse("automacoes:ops_center"))

        self.assertIn(response.status_code, [301, 302])

    def test_ops_center_authenticated_returns_200(self):
        self.client.login(username="ops_user", password="testpass123")

        response = self.client.get(reverse("automacoes:ops_center"))

        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, "automacoes/ops_center.html")
        self.assertIn("ops", response.context)
