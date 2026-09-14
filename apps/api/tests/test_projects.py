from .base import ApiTestCase


class ProjectTests(ApiTestCase):
    def test_list_includes_persisted_inactive_project(self):
        response = self.client.get("/api/v1/projects/")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["count"], 2)
        self.assertEqual([p["id"] for p in response.json()["results"]], [self.project.pk, self.empty_project.pk])
        self.assertFalse(response.json()["results"][1]["active"])

    def test_detail(self):
        response = self.client.get(f"/api/v1/projects/{self.project.pk}/")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json(), {"id": self.project.pk, "name": "First", "client": None, "active": True})

    def test_missing_project(self):
        self.assert_error(self.client.get("/api/v1/projects/999999/"), 404, "not_found")

    def test_project_pagination(self):
        data = self.client.get("/api/v1/projects/?page=2&page_size=1").json()
        self.assertEqual(data["results"][0]["id"], self.empty_project.pk)
        self.assertEqual(data["total_pages"], 2)
