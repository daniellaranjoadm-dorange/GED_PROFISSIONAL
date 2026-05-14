from datetime import timedelta

from django.utils import timezone

from apps.automacoes.models import RuntimeMetricSnapshot


class RuntimeMetricsDashboardService:
    """
    Read-only dashboard layer for persisted runtime metric snapshots.

    SQLite-safe:
    - no raw SQL
    - no window functions
    - no database-specific date truncation
    """

    DEFAULT_LIMIT = 24

    @classmethod
    def build_dashboard(cls, limit=None):
        limit = int(limit or cls.DEFAULT_LIMIT)

        snapshots = list(
            RuntimeMetricSnapshot.objects.order_by("-captured_at")[:limit]
        )
        chronological = list(reversed(snapshots))

        latest = snapshots[0] if snapshots else None
        previous = snapshots[1] if len(snapshots) > 1 else None

        return {
            "latest": latest,
            "previous": previous,
            "summary": cls.summary(latest, previous),
            "trend": cls.trend(chronological),
            "timeline": snapshots,
            "count": len(snapshots),
            "updated_at": timezone.now(),
        }

    @classmethod
    def summary(cls, latest, previous=None):
        if not latest:
            return {
                "has_data": False,
                "runtime_score": 0,
                "runtime_status": "unknown",
                "score_delta": 0,
                "success_rate": 0,
                "active_alerts": 0,
                "failed_jobs": 0,
                "running_jobs": 0,
                "scheduler_enabled": 0,
            }

        score_delta = 0
        if previous:
            score_delta = latest.runtime_score - previous.runtime_score

        return {
            "has_data": True,
            "runtime_score": latest.runtime_score,
            "runtime_status": latest.runtime_status,
            "score_delta": score_delta,
            "success_rate": latest.success_rate,
            "active_alerts": latest.active_alerts,
            "failed_jobs": latest.failed_jobs,
            "running_jobs": latest.running_jobs,
            "scheduler_enabled": latest.scheduler_enabled,
        }

    @classmethod
    def trend(cls, snapshots):
        labels = []
        scores = []
        success_rates = []
        alerts = []
        failed_jobs = []

        for item in snapshots:
            labels.append(item.captured_at.strftime("%H:%M"))
            scores.append(item.runtime_score)
            success_rates.append(round(item.success_rate or 0, 2))
            alerts.append(item.active_alerts)
            failed_jobs.append(item.failed_jobs)

        return {
            "labels": labels,
            "scores": scores,
            "success_rates": success_rates,
            "alerts": alerts,
            "failed_jobs": failed_jobs,
        }

    @classmethod
    def recent_window(cls, hours=24):
        since = timezone.now() - timedelta(hours=hours)
        return RuntimeMetricSnapshot.objects.filter(captured_at__gte=since).order_by("-captured_at")
