from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from django.utils import timezone

from apps.automacoes.models import RuntimeMetricSnapshot
from apps.automacoes.services.ops_center_service import OperationsCenterService


@dataclass(frozen=True)
class RuntimeMetricPayload:
    runtime_score: int
    runtime_status: str
    active_alerts: int
    failed_jobs: int
    running_jobs: int
    stale_scheduler_states: int
    jobs_today: int
    success_today: int
    failed_today: int
    success_rate: float
    avg_duration: float | None
    scheduler_total: int
    scheduler_enabled: int
    scheduler_disabled: int
    total_jobs: int
    total_alerts: int


class RuntimeMetricsService:
    """
    Persisted runtime metrics layer.

    This service stores lightweight operational snapshots for trend analysis.
    It is SQLite-friendly and intentionally avoids heavy indexes or complex locks.
    """

    @classmethod
    def collect_payload(cls) -> RuntimeMetricPayload:
        dashboard = OperationsCenterService.build_dashboard()

        runtime = dashboard.get("runtime", {})
        jobs = dashboard.get("jobs", {})
        scheduler = dashboard.get("scheduler", {})
        kpis = dashboard.get("kpis", {})

        return RuntimeMetricPayload(
            runtime_score=int(runtime.get("score") or 0),
            runtime_status=str(runtime.get("status") or "unknown"),
            active_alerts=int(runtime.get("active_alerts") or 0),
            failed_jobs=int(runtime.get("failed_jobs") or 0),
            running_jobs=int(runtime.get("running_jobs") or 0),
            stale_scheduler_states=int(runtime.get("stale_scheduler_states") or 0),
            jobs_today=int(jobs.get("total_today") or 0),
            success_today=int(jobs.get("success_today") or 0),
            failed_today=int(jobs.get("failed_today") or 0),
            success_rate=float(jobs.get("success_rate") or 0),
            avg_duration=cls._safe_float_or_none(jobs.get("avg_duration")),
            scheduler_total=int(scheduler.get("total") or 0),
            scheduler_enabled=int(scheduler.get("enabled") or 0),
            scheduler_disabled=int(scheduler.get("disabled") or 0),
            total_jobs=int(kpis.get("total_jobs") or 0),
            total_alerts=int(kpis.get("total_alerts") or 0),
        )

    @classmethod
    def create_snapshot(cls, source: str = "manual") -> RuntimeMetricSnapshot:
        payload = cls.collect_payload()

        return RuntimeMetricSnapshot.objects.create(
            source=source,
            runtime_score=payload.runtime_score,
            runtime_status=payload.runtime_status,
            active_alerts=payload.active_alerts,
            failed_jobs=payload.failed_jobs,
            running_jobs=payload.running_jobs,
            stale_scheduler_states=payload.stale_scheduler_states,
            jobs_today=payload.jobs_today,
            success_today=payload.success_today,
            failed_today=payload.failed_today,
            success_rate=payload.success_rate,
            avg_duration=payload.avg_duration,
            scheduler_total=payload.scheduler_total,
            scheduler_enabled=payload.scheduler_enabled,
            scheduler_disabled=payload.scheduler_disabled,
            total_jobs=payload.total_jobs,
            total_alerts=payload.total_alerts,
        )

    @classmethod
    def latest_snapshots(cls, limit: int = 24):
        safe_limit = max(1, min(int(limit or 24), 200))
        return RuntimeMetricSnapshot.objects.order_by("-captured_at")[:safe_limit]

    @classmethod
    def trend_summary(cls, limit: int = 24) -> dict[str, Any]:
        snapshots = list(cls.latest_snapshots(limit))

        if not snapshots:
            return {
                "has_data": False,
                "count": 0,
                "latest": None,
                "avg_score": 0,
                "min_score": 0,
                "max_score": 0,
                "latest_status": "unknown",
                "timeline": [],
            }

        scores = [item.runtime_score for item in snapshots]
        latest = snapshots[0]

        timeline = [
            {
                "captured_at": item.captured_at,
                "runtime_score": item.runtime_score,
                "runtime_status": item.runtime_status,
                "active_alerts": item.active_alerts,
                "failed_jobs": item.failed_jobs,
                "success_rate": item.success_rate,
            }
            for item in reversed(snapshots)
        ]

        return {
            "has_data": True,
            "count": len(snapshots),
            "latest": latest,
            "avg_score": round(sum(scores) / len(scores), 2),
            "min_score": min(scores),
            "max_score": max(scores),
            "latest_status": latest.runtime_status,
            "timeline": timeline,
        }

    @staticmethod
    def _safe_float_or_none(value):
        if value is None:
            return None
        try:
            return float(value)
        except (TypeError, ValueError):
            return None
