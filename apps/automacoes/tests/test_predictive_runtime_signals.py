from django.test import TestCase

from apps.automacoes.models import RuntimeMetricSnapshot
from apps.automacoes.services.predictive_runtime_signals import PredictiveRuntimeSignalsService


class PredictiveRuntimeSignalsServiceTests(TestCase):
    def test_build_dashboard_returns_expected_sections(self):
        dashboard = PredictiveRuntimeSignalsService.build_dashboard()

        self.assertIn("risk", dashboard)
        self.assertIn("stability", dashboard)
        self.assertIn("warnings", dashboard)
        self.assertIn("failure_forecast", dashboard)
        self.assertIn("alert_acceleration", dashboard)

    def test_low_risk_when_runtime_is_healthy(self):
        RuntimeMetricSnapshot.objects.create(
            runtime_score=100,
            runtime_status="healthy",
            active_alerts=0,
            failed_jobs=0,
            stale_scheduler_states=0,
        )

        dashboard = PredictiveRuntimeSignalsService.build_dashboard()

        self.assertEqual(dashboard["risk"]["level"], "low")

    def test_risk_increases_when_runtime_degrades(self):
        RuntimeMetricSnapshot.objects.create(
            runtime_score=95,
            runtime_status="healthy",
            active_alerts=0,
            failed_jobs=0,
            stale_scheduler_states=0,
        )
        RuntimeMetricSnapshot.objects.create(
            runtime_score=50,
            runtime_status="critical",
            active_alerts=8,
            failed_jobs=5,
            stale_scheduler_states=2,
        )

        dashboard = PredictiveRuntimeSignalsService.build_dashboard()

        self.assertIn(dashboard["risk"]["level"], ["high", "critical"])
        self.assertTrue(dashboard["warnings"])
