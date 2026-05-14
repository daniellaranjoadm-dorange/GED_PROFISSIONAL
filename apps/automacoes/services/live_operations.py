from __future__ import annotations

from django.utils import timezone

from apps.automacoes.services.ops_center_service import OperationsCenterService
from apps.automacoes.services.runtime_events import RuntimeEventStreamService
from apps.automacoes.services.runtime_metrics_dashboard import RuntimeMetricsDashboardService
from apps.automacoes.services.runtime_trend_analytics import RuntimeTrendAnalyticsService
from apps.automacoes.services.predictive_runtime_signals import PredictiveRuntimeSignalsService


class LiveOperationsService:
    """
    Read-only live operations aggregation layer.

    Designed for HTMX/polling endpoints:
    - no writes
    - no scheduler execution
    - no healing execution
    - safe for frequent refresh
    """

    @classmethod
    def build_payload(cls) -> dict:
        return {
            "ops": OperationsCenterService.build_dashboard(),
            "runtime_events": RuntimeEventStreamService.build_stream(limit=15),
            "runtime_events_summary": RuntimeEventStreamService.summary(),
            "runtime_metrics_dashboard": RuntimeMetricsDashboardService.build_dashboard(limit=20),
            "runtime_trends": RuntimeTrendAnalyticsService.build_dashboard(limit=30),
            "predictive_runtime": PredictiveRuntimeSignalsService.build_dashboard(),
            "live": {
                "status": "online",
                "label": "Live Operations",
                "refreshed_at": timezone.now(),
            },
        }
