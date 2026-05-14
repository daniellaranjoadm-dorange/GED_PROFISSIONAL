from django.db.models import Avg, Count
from django.utils import timezone

from apps.automacoes.models import JobExecution, RuntimeAlert, SchedulerState


class OperationsCenterService:
    """
    Aggregation layer for the Unified Operations Center.

    This service is intentionally read-only:
    it does not start jobs, heal runtime state, or mutate scheduler data.
    """

    JOB_SUCCESS_STATUSES = ("success", "sucesso", "completed", "done", "ok")
    JOB_FAILED_STATUSES = ("failed", "failure", "erro", "error")
    JOB_RUNNING_STATUSES = ("running", "iniciado", "processing", "started")

    ALERT_RESOLVED_FIELDS = ("resolved", "is_resolved", "resolvido")
    DATE_FIELDS = ("created_at", "criado_em", "started_at", "iniciado_em")
    JOB_NAME_FIELDS = ("job_name", "name", "nome", "task_name")
    DURATION_FIELDS = ("duration", "duration_seconds", "duracao", "duracao_segundos")
    UPDATED_FIELDS = ("updated_at", "atualizado_em", "heartbeat", "last_heartbeat")
    ALERT_CREATED_FIELDS = ("created_at", "criado_em", "timestamp")
    ALERT_LEVEL_FIELDS = ("level", "severity", "nivel")
    ALERT_MESSAGE_FIELDS = ("message", "mensagem", "description", "descricao")

    @classmethod
    def build_dashboard(cls):
        return {
            "runtime": cls.runtime_health(),
            "scheduler": cls.scheduler_status(),
            "jobs": cls.job_metrics(),
            "alerts": cls.alert_metrics(),
            "kpis": cls.global_kpis(),
            "updated_at": timezone.now(),
        }

    @classmethod
    def runtime_health(cls):
        active_alerts = cls._active_alerts_qs().count()
        failed_jobs = cls._jobs_by_status(cls.JOB_FAILED_STATUSES).count()
        running_jobs = cls._jobs_by_status(cls.JOB_RUNNING_STATUSES).count()
        stale_scheduler_states = cls._stale_scheduler_states_count()

        score = 100
        score -= min(active_alerts * 10, 40)
        score -= min(failed_jobs * 5, 30)
        score -= min(running_jobs * 2, 10)
        score -= min(stale_scheduler_states * 10, 30)
        score = max(score, 0)

        if score >= 85:
            status = "healthy"
        elif score >= 60:
            status = "warning"
        else:
            status = "critical"

        return {
            "score": score,
            "status": status,
            "active_alerts": active_alerts,
            "failed_jobs": failed_jobs,
            "running_jobs": running_jobs,
            "stale_scheduler_states": stale_scheduler_states,
        }

    @classmethod
    def scheduler_status(cls):
        qs = SchedulerState.objects.all()

        enabled = cls._count_boolean(qs, "enabled", True)
        disabled = cls._count_boolean(qs, "enabled", False)

        order_field = cls._first_existing_field(SchedulerState, cls.UPDATED_FIELDS)
        latest_states = qs.order_by(f"-{order_field}")[:10] if order_field else qs[:10]

        return {
            "total": qs.count(),
            "enabled": enabled,
            "disabled": disabled,
            "latest_states": latest_states,
        }

    @classmethod
    def job_metrics(cls):
        qs = JobExecution.objects.all()
        date_field = cls._first_existing_field(JobExecution, cls.DATE_FIELDS)
        duration_field = cls._first_existing_field(JobExecution, cls.DURATION_FIELDS)
        today = timezone.localdate()

        jobs_today = qs
        if date_field:
            jobs_today = qs.filter(**{f"{date_field}__date": today})

        total_today = jobs_today.count()
        success_today = cls._filter_by_status(jobs_today, cls.JOB_SUCCESS_STATUSES).count()
        failed_today = cls._filter_by_status(jobs_today, cls.JOB_FAILED_STATUSES).count()
        running = cls._jobs_by_status(cls.JOB_RUNNING_STATUSES).count()

        avg_duration = None
        if duration_field:
            avg_duration = jobs_today.aggregate(avg=Avg(duration_field))["avg"]

        order_field = date_field or cls._first_existing_field(JobExecution, ("id",))
        latest_jobs = qs.order_by(f"-{order_field}")[:10] if order_field else qs[:10]

        success_rate = round((success_today / total_today) * 100, 2) if total_today else 0

        return {
            "total_today": total_today,
            "success_today": success_today,
            "failed_today": failed_today,
            "running": running,
            "success_rate": success_rate,
            "avg_duration": avg_duration,
            "latest_jobs": latest_jobs,
            "name_field": cls._first_existing_field(JobExecution, cls.JOB_NAME_FIELDS),
            "date_field": date_field,
            "duration_field": duration_field,
        }

    @classmethod
    def alert_metrics(cls):
        active = cls._active_alerts_qs()
        order_field = cls._first_existing_field(RuntimeAlert, cls.ALERT_CREATED_FIELDS)
        latest_alerts = RuntimeAlert.objects.all()

        if order_field:
            latest_alerts = latest_alerts.order_by(f"-{order_field}")[:10]
        else:
            latest_alerts = latest_alerts[:10]

        level_field = cls._first_existing_field(RuntimeAlert, cls.ALERT_LEVEL_FIELDS)
        if level_field:
            by_level = active.values(level_field).annotate(total=Count("id")).order_by(level_field)
        else:
            by_level = []

        return {
            "active_total": active.count(),
            "by_level": by_level,
            "latest_alerts": latest_alerts,
            "level_field": level_field,
            "message_field": cls._first_existing_field(RuntimeAlert, cls.ALERT_MESSAGE_FIELDS),
            "date_field": order_field,
        }

    @classmethod
    def global_kpis(cls):
        return {
            "total_jobs": JobExecution.objects.count(),
            "total_scheduler_states": SchedulerState.objects.count(),
            "total_alerts": RuntimeAlert.objects.count(),
            "active_alerts": cls._active_alerts_qs().count(),
        }

    @classmethod
    def _jobs_by_status(cls, statuses):
        return cls._filter_by_status(JobExecution.objects.all(), statuses)

    @classmethod
    def _filter_by_status(cls, qs, statuses):
        if cls._has_field(qs.model, "status"):
            return qs.filter(status__in=statuses)
        return qs.none()

    @classmethod
    def _active_alerts_qs(cls):
        qs = RuntimeAlert.objects.all()
        for field_name in cls.ALERT_RESOLVED_FIELDS:
            if cls._has_field(RuntimeAlert, field_name):
                return qs.filter(**{field_name: False})
        return qs

    @classmethod
    def _stale_scheduler_states_count(cls):
        if cls._has_field(SchedulerState, "last_status"):
            return SchedulerState.objects.filter(last_status__icontains="stale").count()
        if cls._has_field(SchedulerState, "runtime_notes"):
            return SchedulerState.objects.filter(runtime_notes__icontains="stale").count()
        return 0

    @staticmethod
    def _has_field(model, field_name):
        return any(field.name == field_name for field in model._meta.get_fields())

    @classmethod
    def _first_existing_field(cls, model, field_names):
        for field_name in field_names:
            if cls._has_field(model, field_name):
                return field_name
        return None

    @classmethod
    def _count_boolean(cls, qs, field_name, value):
        if cls._has_field(qs.model, field_name):
            return qs.filter(**{field_name: value}).count()
        return 0
