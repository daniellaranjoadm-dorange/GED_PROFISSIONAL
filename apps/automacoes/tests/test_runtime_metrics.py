from django.core.management import call_command
from django.test import TestCase

from apps.automacoes.models import RuntimeMetricSnapshot
from apps.automacoes.services.runtime_metrics import RuntimeMetricsService


class RuntimeMetricsServiceTests(TestCase):
    def test_collect_payload_returns_runtime_fields(self):
        payload = RuntimeMetricsService.collect_payload()

        self.assertGreaterEqual(payload.runtime_score, 0)
        self.assertIsInstance(payload.runtime_status, str)
        self.assertGreaterEqual(payload.active_alerts, 0)

    def test_create_snapshot_persists_metrics(self):
        snapshot = RuntimeMetricsService.create_snapshot(source="test")

        self.assertEqual(RuntimeMetricSnapshot.objects.count(), 1)
        self.assertEqual(snapshot.source, "test")
        self.assertGreaterEqual(snapshot.runtime_score, 0)

    def test_trend_summary_without_data_is_safe(self):
        summary = RuntimeMetricsService.trend_summary()

        self.assertFalse(summary["has_data"])
        self.assertEqual(summary["count"], 0)

    def test_trend_summary_with_data(self):
        RuntimeMetricsService.create_snapshot(source="test")

        summary = RuntimeMetricsService.trend_summary()

        self.assertTrue(summary["has_data"])
        self.assertEqual(summary["count"], 1)
        self.assertIn("avg_score", summary)

    def test_capture_runtime_metrics_command(self):
        call_command("capture_runtime_metrics", source="test-command")

        self.assertEqual(RuntimeMetricSnapshot.objects.count(), 1)
        self.assertEqual(RuntimeMetricSnapshot.objects.first().source, "test-command")
