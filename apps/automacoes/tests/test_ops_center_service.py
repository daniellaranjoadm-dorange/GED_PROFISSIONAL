from django.test import TestCase

from apps.automacoes.services.ops_center_service import OperationsCenterService


class OperationsCenterServiceTests(TestCase):
    def test_build_dashboard_returns_expected_sections(self):
        dashboard = OperationsCenterService.build_dashboard()

        self.assertIn("runtime", dashboard)
        self.assertIn("scheduler", dashboard)
        self.assertIn("jobs", dashboard)
        self.assertIn("alerts", dashboard)
        self.assertIn("kpis", dashboard)
        self.assertIn("updated_at", dashboard)

    def test_runtime_health_returns_score_and_status(self):
        runtime = OperationsCenterService.runtime_health()

        self.assertIn("score", runtime)
        self.assertIn("status", runtime)
        self.assertGreaterEqual(runtime["score"], 0)
        self.assertLessEqual(runtime["score"], 100)
        self.assertIn(runtime["status"], ["healthy", "warning", "critical"])

    def test_job_metrics_returns_expected_keys(self):
        metrics = OperationsCenterService.job_metrics()

        self.assertIn("total_today", metrics)
        self.assertIn("success_today", metrics)
        self.assertIn("failed_today", metrics)
        self.assertIn("running", metrics)
        self.assertIn("success_rate", metrics)
        self.assertIn("latest_jobs", metrics)
