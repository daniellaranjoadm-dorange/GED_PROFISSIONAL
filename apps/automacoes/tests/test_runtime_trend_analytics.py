from django.test import TestCase

from apps.automacoes.models import RuntimeMetricSnapshot
from apps.automacoes.services.runtime_trend_analytics import RuntimeTrendAnalyticsService


class RuntimeTrendAnalyticsServiceTests(TestCase):
    def test_build_dashboard_without_snapshots_is_safe(self):
        dashboard = RuntimeTrendAnalyticsService.build_dashboard()

        self.assertIn("summary", dashboard)
        self.assertIn("score_trend", dashboard)
        self.assertIn("anomalies", dashboard)
        self.assertEqual(dashboard["summary"]["total_snapshots"], 0)

    def test_score_trend_detects_degradation(self):
        RuntimeMetricSnapshot.objects.create(
            source="test",
            runtime_score=95,
            runtime_status="healthy",
        )
        RuntimeMetricSnapshot.objects.create(
            source="test",
            runtime_score=70,
            runtime_status="warning",
        )

        dashboard = RuntimeTrendAnalyticsService.build_dashboard()

        self.assertEqual(dashboard["score_trend"]["direction"], "degrading")
        self.assertGreaterEqual(len(dashboard["anomalies"]), 1)

    def test_alert_trend_detects_improvement_when_alerts_drop(self):
        RuntimeMetricSnapshot.objects.create(
            source="test",
            runtime_score=80,
            runtime_status="warning",
            active_alerts=5,
        )
        RuntimeMetricSnapshot.objects.create(
            source="test",
            runtime_score=90,
            runtime_status="healthy",
            active_alerts=1,
        )

        dashboard = RuntimeTrendAnalyticsService.build_dashboard()

        self.assertEqual(dashboard["alert_trend"]["direction"], "improving")
