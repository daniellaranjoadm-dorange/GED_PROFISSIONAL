class SchedulerState(models.Model):
    STATUS_IDLE = "IDLE"
    STATUS_RUNNING = "RUNNING"
    STATUS_SUCCESS = "SUCCESS"
    STATUS_FAILED = "FAILED"
    STATUS_DISABLED = "DISABLED"

    STATUS_CHOICES = [
        (STATUS_IDLE, "Idle"),
        (STATUS_RUNNING, "Running"),
        (STATUS_SUCCESS, "Success"),
        (STATUS_FAILED, "Failed"),
        (STATUS_DISABLED, "Disabled"),
    ]

    job_name = models.CharField(max_length=255, unique=True, db_index=True)
    enabled = models.BooleanField(default=True, db_index=True)

    last_run_at = models.DateTimeField(blank=True, null=True)
    next_run_at = models.DateTimeField(blank=True, null=True)
    last_success_at = models.DateTimeField(blank=True, null=True)
    last_failure_at = models.DateTimeField(blank=True, null=True)

    last_status = models.CharField(
        max_length=20,
        choices=STATUS_CHOICES,
        default=STATUS_IDLE,
        db_index=True,
    )

    heartbeat_at = models.DateTimeField(blank=True, null=True)
    runtime_notes = models.TextField(blank=True)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["job_name"]
        indexes = [
            models.Index(fields=["enabled", "last_status"]),
            models.Index(fields=["heartbeat_at"]),
            models.Index(fields=["next_run_at"]),
        ]

    def __str__(self):
        return f"{self.job_name} [{self.last_status}]"
