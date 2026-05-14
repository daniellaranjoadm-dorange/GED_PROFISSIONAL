from django.test import TestCase

from apps.automacoes.models import RuntimeMetricSnapshot
from apps.automacoes.services.runtime_metrics_dashboard import RuntimeMetricsDashboardService


class RuntimeMetricsDashboardServiceTests(TestCase):
    def test_dashboard_without_snapshots_is_safe(self):
        dashboard = RuntimeMetricsDashboardService.build_dashboard()

        self.assertIn("summary", dashboard)
        self.assertFalse(dashboard["summary"]["has_data"])
        self.assertEqual(dashboard["summary"]["runtime_score"], 0)

    def test_dashboard_with_snapshots_returns_summary_and_trend(self):
        RuntimeMetricSnapshot.objects.create(
            source="test",
            runtime_score=90,
            runtime_status="healthy",
            success_rate=95,
        )
        RuntimeMetricSnapshot.objects.create(
            source="test",
            runtime_score=80,
            runtime_status="warning",
            success_rate=85,
        )

        dashboard = RuntimeMetricsDashboardService.build_dashboard()

        self.assertTrue(dashboard["summary"]["has_data"])
        self.assertIn("trend", dashboard)
        self.assertGreaterEqual(dashboard["count"], 1)
