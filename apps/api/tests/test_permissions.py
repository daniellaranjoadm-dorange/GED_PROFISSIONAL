from django.contrib.auth import get_user_model

from .base import ApiTestCase


class PermissionTests(ApiTestCase):
    def endpoints(self):
        return ("/api/v1/projects/", f"/api/v1/projects/{self.project.pk}/", "/api/v1/documents/", f"/api/v1/documents/{self.old.pk}/")

    def test_anonymous(self):
        self.client.logout()
        for endpoint in self.endpoints():
            self.assert_error(self.client.get(endpoint), 401, "authentication_required")

    def test_without_permission(self):
        user = get_user_model().objects.create_user(username="denied")
        self.client.force_login(user)
        for endpoint in self.endpoints():
            self.assert_error(self.client.get(endpoint), 403, "permission_denied")

    def test_authorized(self):
        for endpoint in self.endpoints():
            self.assertEqual(self.client.get(endpoint).status_code, 200)

    def test_master_and_superuser(self):
        for flag in ("is_master", "is_superuser"):
            user = get_user_model().objects.create_user(username=flag, **{flag: True})
            self.client.force_login(user)
            self.assertEqual(self.client.get("/api/v1/documents/").status_code, 200)
