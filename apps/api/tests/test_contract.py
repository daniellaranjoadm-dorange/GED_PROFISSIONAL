from django.db import connection
from django.test import Client
from django.test.utils import CaptureQueriesContext

from apps.api.selectors import documents
from apps.api.serializers import serialize_document

from .base import ApiTestCase


class ContractTests(ApiTestCase):
    def test_explicit_document_schema(self):
        data = self.client.get(f"/api/v1/documents/{self.old.pk}/").json()
        self.assertEqual(data, {
            "id": self.old.pk, "master_id": self.master.pk, "document_number": "DOC",
            "title": "Old", "revision": "0", "current_revision_id": self.current.pk,
            "current_revision": "1", "is_current_revision": False,
            "project": {"id": self.project.pk, "name": "First"},
            "discipline": "Hull", "document_type": "Drawing", "status": "Received",
        })

    def test_nullable_metadata(self):
        data = self.client.get(f"/api/v1/documents/{self.current.pk}/").json()
        for key in ("discipline", "document_type", "status"):
            self.assertIsNone(data[key])

    def test_no_write_queries_and_no_automation_reads(self):
        endpoints = ("/api/v1/projects/", f"/api/v1/projects/{self.project.pk}/", "/api/v1/documents/", f"/api/v1/documents/{self.old.pk}/")
        for method in ("get", "post", "put", "patch", "delete", "head", "options"):
            for endpoint in endpoints:
                with self.subTest(method=method, endpoint=endpoint):
                    with CaptureQueriesContext(connection) as captured:
                        response = getattr(self.client, method)(endpoint)
                    self.assertEqual(response.status_code, 200 if method == "get" else 405)
                    if method != "get":
                        self.assertEqual(response["Allow"], "GET")
                        if method != "head":
                            self.assert_error(response, 405, "method_not_allowed")
                    for query in captured:
                        sql = query["sql"].strip().upper()
                        self.assertTrue(sql.startswith("SELECT"), sql)
                        self.assertNotIn("AUTOMACOES_", sql)

    def test_csrf_remains_enforced(self):
        client = Client(enforce_csrf_checks=True)
        client.force_login(self.user)
        for method in ("post", "put", "patch", "delete"):
            self.assertEqual(getattr(client, method)("/api/v1/documents/").status_code, 403)

    def test_serialization_has_no_per_row_queries(self):
        with self.assertNumQueries(1):
            data = [serialize_document(doc) for doc in documents()]
        self.assertEqual(len(data), 2)

    def test_private_cache_policy(self):
        response = self.client.get("/api/v1/documents/")
        self.assertEqual(response["Cache-Control"], "private, no-store")
