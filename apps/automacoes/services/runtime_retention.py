from __future__ import annotations

from dataclasses import dataclass
from datetime import timedelta

from django.utils import timezone

from apps.automacoes.models import RuntimeMetricSnapshot


@dataclass(frozen=True)
class RuntimeRetentionResult:
    model: str
    deleted: int
    cutoff: object


class RuntimeRetentionService:
    """
    SQLite-safe runtime retention policies.

    Current scope:
    - RuntimeMetricSnapshot retention

    Notes:
    - avoids raw SQL
    - avoids database-specific syntax
    - performs bounded queryset deletes
    """

    DEFAULT_SNAPSHOT_DAYS = 90

    @classmethod
    def cleanup_snapshots(cls, days: int | None = None, dry_run: bool = False) -> RuntimeRetentionResult:
        days = int(days or cls.DEFAULT_SNAPSHOT_DAYS)
        cutoff = timezone.now() - timedelta(days=days)

        queryset = RuntimeMetricSnapshot.objects.filter(created_at__lt=cutoff)
        count = queryset.count()

        if not dry_run and count:
            queryset.delete()

        return RuntimeRetentionResult(
            model="RuntimeMetricSnapshot",
            deleted=count,
            cutoff=cutoff,
        )

    @classmethod
    def cleanup_all(cls, days: int | None = None, dry_run: bool = False) -> dict:
        snapshot_result = cls.cleanup_snapshots(days=days, dry_run=dry_run)

        return {
            "dry_run": dry_run,
            "results": [
                {
                    "model": snapshot_result.model,
                    "deleted": snapshot_result.deleted,
                    "cutoff": snapshot_result.cutoff.isoformat(),
                }
            ],
            "total_deleted": snapshot_result.deleted,
        }
