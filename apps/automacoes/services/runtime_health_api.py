from __future__ import annotations

from django.utils import timezone

from apps.automacoes.services.ops_center_service import OperationsCenterService
from apps.automacoes.services.runtime_events import RuntimeEventStreamService
from apps.automacoes.services.runtime_metrics_dashboard import RuntimeMetricsDashboardService
from apps.automacoes.services.predictive_runtime_signals import PredictiveRuntimeSignalsService


class RuntimeHealthAPIService:
    """
    JSON-safe runtime health aggregation.

    Designed for:
    - internal APIs
    - monitoring integrations
    - future Grafana/Prometheus bridge
    - lightweight frontend polling
    """

    @classmethod
    def health(cls) -> dict:
        ops = OperationsCenterService.build_dashboard()
        predictive = PredictiveRuntimeSignalsService.build_dashboard()

        return {
            "status": ops.get("runtime", {}).get("status", "unknown"),
            "score": ops.get("runtime", {}).get("score", 0),
            "risk": predictive.get("risk", {}),
            "active_alerts": ops.get("runtime", {}).get("active_alerts", 0),
            "running_jobs": ops.get("runtime", {}).get("running_jobs", 0),
            "failed_jobs": ops.get("runtime", {}).get("failed_jobs", 0),
            "scheduler_stale": ops.get("runtime", {}).get("stale_scheduler_states", 0),
            "generated_at": timezone.now().isoformat(),
        }

    @classmethod
    def metrics(cls) -> dict:
        return {
            "dashboard": RuntimeMetricsDashboardService.build_dashboard(limit=50),
            "generated_at": timezone.now().isoformat(),
        }

    @classmethod
    def events(cls) -> dict:
        return {
            "events": RuntimeEventStreamService.build_stream(limit=50),
            "summary": RuntimeEventStreamService.summary(),
            "generated_at": timezone.now().isoformat(),
        }
