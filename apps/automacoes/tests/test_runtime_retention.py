from datetime import timedelta

from django.test import TestCase
from django.utils import timezone

from apps.automacoes.models import RuntimeMetricSnapshot
from apps.automacoes.services.runtime_retention import RuntimeRetentionService


class RuntimeRetentionServiceTests(TestCase):
    def test_cleanup_snapshots_dry_run_does_not_delete(self):
        snapshot = RuntimeMetricSnapshot.objects.create(
            runtime_score=100,
            runtime_status="healthy",
            active_alerts=0,
            failed_jobs=0,
            stale_scheduler_states=0,
        )
        RuntimeMetricSnapshot.objects.filter(pk=snapshot.pk).update(
            captured_at=timezone.now() - timedelta(days=120)
        )

        result = RuntimeRetentionService.cleanup_snapshots(days=90, dry_run=True)

        self.assertEqual(result.deleted, 1)
        self.assertEqual(RuntimeMetricSnapshot.objects.count(), 1)

    def test_cleanup_snapshots_deletes_old_rows(self):
        snapshot = RuntimeMetricSnapshot.objects.create(
            runtime_score=100,
            runtime_status="healthy",
            active_alerts=0,
            failed_jobs=0,
            stale_scheduler_states=0,
        )
        RuntimeMetricSnapshot.objects.filter(pk=snapshot.pk).update(
            captured_at=timezone.now() - timedelta(days=120)
        )

        result = RuntimeRetentionService.cleanup_snapshots(days=90, dry_run=False)

        self.assertEqual(result.deleted, 1)
        self.assertEqual(RuntimeMetricSnapshot.objects.count(), 0)
