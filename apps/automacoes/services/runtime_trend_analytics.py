from __future__ import annotations

from dataclasses import dataclass
from statistics import mean
from typing import Iterable

from django.utils import timezone

from apps.automacoes.models import RuntimeMetricSnapshot


@dataclass(frozen=True)
class TrendDelta:
    current: float
    previous: float
    delta: float
    direction: str
    label: str


class RuntimeTrendAnalyticsService:
    """
    Historical operational intelligence built from RuntimeMetricSnapshot.

    Read-only, SQLite-safe and intentionally lightweight:
    - no writes
    - no raw SQL
    - no database-specific functions
    """

    DEFAULT_LIMIT = 50

    @classmethod
    def build_dashboard(cls, limit: int = DEFAULT_LIMIT) -> dict:
        snapshots = list(
            RuntimeMetricSnapshot.objects.all().order_by("-captured_at")[: max(limit, 2)]
        )

        chronological = list(reversed(snapshots))

        return {
            "summary": cls.summary(snapshots),
            "score_trend": cls.score_trend(snapshots),
            "alert_trend": cls.alert_trend(snapshots),
            "failure_trend": cls.failure_trend(snapshots),
            "scheduler_trend": cls.scheduler_trend(snapshots),
            "anomalies": cls.detect_anomalies(snapshots),
            "series": cls.series(chronological),
            "latest_snapshots": snapshots[:10],
            "generated_at": timezone.now(),
        }

    @classmethod
    def summary(cls, snapshots: list[RuntimeMetricSnapshot]) -> dict:
        if not snapshots:
            return {
                "total_snapshots": 0,
                "latest_score": 0,
                "latest_status": "unknown",
                "avg_score": 0,
                "min_score": 0,
                "max_score": 0,
                "health_label": "Sem histórico",
            }

        scores = [snapshot.runtime_score for snapshot in snapshots]

        latest = snapshots[0]
        avg_score = round(mean(scores), 2)

        if avg_score >= 85:
            health_label = "Estável"
        elif avg_score >= 60:
            health_label = "Atenção"
        else:
            health_label = "Crítico"

        return {
            "total_snapshots": len(snapshots),
            "latest_score": latest.runtime_score,
            "latest_status": latest.runtime_status,
            "avg_score": avg_score,
            "min_score": min(scores),
            "max_score": max(scores),
            "health_label": health_label,
        }

    @classmethod
    def score_trend(cls, snapshots: list[RuntimeMetricSnapshot]) -> dict:
        return cls._trend(
            snapshots=snapshots,
            field="runtime_score",
            higher_is_better=True,
            stable_threshold=2,
        )

    @classmethod
    def alert_trend(cls, snapshots: list[RuntimeMetricSnapshot]) -> dict:
        return cls._trend(
            snapshots=snapshots,
            field="active_alerts",
            higher_is_better=False,
            stable_threshold=1,
        )

    @classmethod
    def failure_trend(cls, snapshots: list[RuntimeMetricSnapshot]) -> dict:
        return cls._trend(
            snapshots=snapshots,
            field="failed_jobs",
            higher_is_better=False,
            stable_threshold=1,
        )

    @classmethod
    def scheduler_trend(cls, snapshots: list[RuntimeMetricSnapshot]) -> dict:
        return cls._trend(
            snapshots=snapshots,
            field="stale_scheduler_states",
            higher_is_better=False,
            stable_threshold=1,
        )

    @classmethod
    def detect_anomalies(cls, snapshots: list[RuntimeMetricSnapshot]) -> list[dict]:
        if not snapshots:
            return []

        latest = snapshots[0]
        anomalies = []

        if latest.runtime_score < 60:
            anomalies.append({
                "severity": "critical",
                "kind": "runtime_score",
                "message": "Runtime score crítico detectado.",
            })
        elif latest.runtime_score < 85:
            anomalies.append({
                "severity": "warning",
                "kind": "runtime_score",
                "message": "Runtime score em zona de atenção.",
            })

        if latest.active_alerts >= 5:
            anomalies.append({
                "severity": "warning",
                "kind": "active_alerts",
                "message": "Volume elevado de alertas ativos.",
            })

        if latest.failed_jobs >= 3:
            anomalies.append({
                "severity": "critical",
                "kind": "failed_jobs",
                "message": "Acúmulo relevante de jobs falhos.",
            })

        if latest.stale_scheduler_states > 0:
            anomalies.append({
                "severity": "warning",
                "kind": "scheduler_stale",
                "message": "Scheduler state stale detectado.",
            })

        score = cls.score_trend(snapshots)
        if score["direction"] == "degrading" and abs(score["delta"]) >= 10:
            anomalies.append({
                "severity": "warning",
                "kind": "score_degradation",
                "message": "Degradação operacional recente detectada.",
            })

        return anomalies

    @classmethod
    def series(cls, snapshots: list[RuntimeMetricSnapshot]) -> dict:
        return {
            "labels": [
                snapshot.captured_at.strftime("%H:%M")
                for snapshot in snapshots
            ],
            "runtime_score": [
                snapshot.runtime_score
                for snapshot in snapshots
            ],
            "active_alerts": [
                snapshot.active_alerts
                for snapshot in snapshots
            ],
            "failed_jobs": [
                snapshot.failed_jobs
                for snapshot in snapshots
            ],
            "stale_scheduler_states": [
                snapshot.stale_scheduler_states
                for snapshot in snapshots
            ],
        }

    @classmethod
    def _trend(
        cls,
        snapshots: list[RuntimeMetricSnapshot],
        field: str,
        higher_is_better: bool,
        stable_threshold: float,
    ) -> dict:
        if len(snapshots) < 2:
            return {
                "current": 0,
                "previous": 0,
                "delta": 0,
                "direction": "stable",
                "label": "Sem dados suficientes",
            }

        current = float(getattr(snapshots[0], field, 0) or 0)
        previous = float(getattr(snapshots[1], field, 0) or 0)
        delta = round(current - previous, 2)

        if abs(delta) <= stable_threshold:
            direction = "stable"
            label = "Estável"
        else:
            improved = delta > 0 if higher_is_better else delta < 0
            direction = "improving" if improved else "degrading"
            label = "Melhorando" if improved else "Degradando"

        return {
            "current": current,
            "previous": previous,
            "delta": delta,
            "direction": direction,
            "label": label,
        }
