from apps.documentos.models import Documento

from .base import ApiTestCase


class DocumentTests(ApiTestCase):
    def test_list_visibility_and_nullable_project(self):
        response = self.client.get("/api/v1/documents/")
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertEqual(data["count"], 2)
        self.assertEqual([d["id"] for d in data["results"]], [self.old.pk, self.current.pk])
        self.assertEqual(data["results"][0]["project"], {"id": self.project.pk, "name": "First"})
        self.assertIsNone(data["results"][1]["project"])

    def test_detail_revision_identity(self):
        old = self.client.get(f"/api/v1/documents/{self.old.pk}/").json()
        current = self.client.get(f"/api/v1/documents/{self.current.pk}/").json()
        self.assertEqual(old["id"], self.old.pk)
        self.assertEqual(old["revision"], "0")
        self.assertEqual(old["master_id"], self.master.pk)
        self.assertEqual(old["current_revision_id"], self.current.pk)
        self.assertEqual(old["current_revision"], "1")
        self.assertFalse(old["is_current_revision"])
        self.assertTrue(current["is_current_revision"])

    def test_missing_and_hidden_documents(self):
        for pk in (999999, self.inactive.pk, self.deleted.pk):
            with self.subTest(pk=pk):
                self.assert_error(self.client.get(f"/api/v1/documents/{pk}/"), 404, "not_found")

    def test_exact_project_filter(self):
        data = self.client.get(f"/api/v1/documents/?project_id={self.project.pk}").json()
        self.assertEqual([d["id"] for d in data["results"]], [self.old.pk])

    def test_existing_empty_project(self):
        response = self.client.get(f"/api/v1/documents/?project_id={self.empty_project.pk}")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json(), {"count": 0, "page": 1, "page_size": 50, "total_pages": 1, "results": []})

    def test_invalid_project_filter(self):
        for value in ("", "HANDY", "-1", "0", "1.5", "999999", "9" * 30):
            with self.subTest(value=value):
                self.assert_error(self.client.get("/api/v1/documents/", {"project_id": value}), 400, "invalid_query")

    def test_unsupported_and_repeated_parameters(self):
        for query in ("project=HANDY", "project=GLP", "project=MR1", "project_id=1&project_id=2", "page=1&page=2"):
            with self.subTest(query=query):
                self.assert_error(self.client.get("/api/v1/documents/?" + query), 400, "invalid_query")

    def test_pagination_order(self):
        for page, pk in ((1, self.old.pk), (2, self.current.pk)):
            response = self.client.get(f"/api/v1/documents/?page={page}&page_size=1")
            self.assertEqual(response.status_code, 200)
            self.assertEqual(response.json(), {
                "count": 2, "page": page, "page_size": 1, "total_pages": 2,
                "results": [self.client.get(f"/api/v1/documents/{pk}/").json()],
            })

    def test_invalid_pagination_and_maximum(self):
        self.assertEqual(self.client.get("/api/v1/documents/?page_size=200").status_code, 200)
        for query in ("page=0", "page=-1", "page=abc", "page=3", "page_size=0", "page_size=201", "page_size=", "page_size=2.5"):
            with self.subTest(query=query):
                self.assert_error(self.client.get("/api/v1/documents/?" + query), 400, "invalid_query")

    def test_absent_master(self):
        doc = Documento.objects.create(codigo="NO-MASTER", titulo="No master")
        data = self.client.get(f"/api/v1/documents/{doc.pk}/").json()
        for key in ("master_id", "current_revision_id", "current_revision"):
            self.assertIsNone(data[key])
        self.assertFalse(data["is_current_revision"])

    def test_missing_or_hidden_or_inconsistent_current_pointer(self):
        for pointer in (None, self.inactive, self.deleted):
            with self.subTest(pointer=pointer):
                self.master.revisao_atual = pointer
                self.master.save(update_fields=["revisao_atual"])
                data = self.client.get(f"/api/v1/documents/{self.old.pk}/").json()
                self.assertIsNone(data["current_revision_id"])
                self.assertIsNone(data["current_revision"])
                self.assertFalse(data["is_current_revision"])
        self.current.mestre = None
        self.current.save(update_fields=["mestre"])
        self.master.revisao_atual = self.current
        self.master.save(update_fields=["revisao_atual"])
        self.assertIsNone(self.client.get(f"/api/v1/documents/{self.old.pk}/").json()["current_revision_id"])
