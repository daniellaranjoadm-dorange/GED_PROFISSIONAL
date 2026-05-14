from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse


class EnterpriseUXOperationsCenterTests(TestCase):
    def setUp(self):
        User = get_user_model()
        self.user = User.objects.create_user(
            username="enterprise_ux_user",
            password="testpass123",
        )

    def test_ops_center_renders_enterprise_sections(self):
        self.client.login(username="enterprise_ux_user", password="testpass123")

        response = self.client.get(reverse("automacoes:ops_center"))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "GED Operational Intelligence")
        self.assertContains(response, "Executive Operations Summary")
