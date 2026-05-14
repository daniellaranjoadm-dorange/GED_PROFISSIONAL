from django.db import models


class RuntimeMetricSnapshot(models.Model):
    """
    Lightweight persisted runtime metrics snapshot.

    SQLite-safe:
    - no custom indexes
    - no constraints beyond simple fields
    - append-only operational history
    """

    source = models.CharField(max_length=40, default="manual")
    captured_at = models.DateTimeField(auto_now_add=True)

    runtime_score = models.PositiveSmallIntegerField(default=0)
    runtime_status = models.CharField(max_length=30, default="unknown")

    active_alerts = models.PositiveIntegerField(default=0)
    failed_jobs = models.PositiveIntegerField(default=0)
    running_jobs = models.PositiveIntegerField(default=0)
    stale_scheduler_states = models.PositiveIntegerField(default=0)

    jobs_today = models.PositiveIntegerField(default=0)
    success_today = models.PositiveIntegerField(default=0)
    failed_today = models.PositiveIntegerField(default=0)
    success_rate = models.FloatField(default=0)
    avg_duration = models.FloatField(null=True, blank=True)

    scheduler_total = models.PositiveIntegerField(default=0)
    scheduler_enabled = models.PositiveIntegerField(default=0)
    scheduler_disabled = models.PositiveIntegerField(default=0)

    total_jobs = models.PositiveIntegerField(default=0)
    total_alerts = models.PositiveIntegerField(default=0)

    class Meta:
        ordering = ["-captured_at"]
        verbose_name = "Runtime Metric Snapshot"
        verbose_name_plural = "Runtime Metric Snapshots"

    def __str__(self):
        return f"{self.captured_at:%Y-%m-%d %H:%M:%S} | {self.runtime_status} | {self.runtime_score}"
