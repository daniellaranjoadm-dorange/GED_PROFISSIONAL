from django.db.models import Avg, Count, Q
from django.utils import timezone

from apps.automacoes.models import JobExecution, RuntimeAlert, SchedulerState


class OperationsCenterService:
    """
    Read-only aggregation layer for the Unified Operations Center.

    Design goals:
    - no writes
    - no scheduler execution
    - no migrations
    - tolerant to field-name differences across runtime models
    - safe for SQLite/dev and PostgreSQL/future
    """

    JOB_SUCCESS_STATUSES = ("success", "sucesso", "completed", "complete", "done", "ok", "finalizado")
    JOB_FAILED_STATUSES = ("failed", "failure", "erro", "error", "falha")
    JOB_RUNNING_STATUSES = ("running", "iniciado", "processing", "started", "executando")

    ALERT_RESOLVED_FIELDS = ("resolved", "is_resolved", "resolvido")
    DATE_FIELDS = ("created_at", "criado_em", "started_at", "iniciado_em", "created")
    JOB_NAME_FIELDS = ("job_name", "name", "nome", "task_name", "codigo", "code")
    DURATION_FIELDS = ("duration", "duration_seconds", "duracao", "duracao_segundos")
    UPDATED_FIELDS = ("updated_at", "atualizado_em", "heartbeat", "last_heartbeat", "last_run_at")
    ALERT_CREATED_FIELDS = ("created_at", "criado_em", "timestamp", "created")
    ALERT_LEVEL_FIELDS = ("level", "severity", "nivel", "tipo")
    ALERT_MESSAGE_FIELDS = ("message", "mensagem", "description", "descricao", "runtime_notes")

    @classmethod
    def build_dashboard(cls):
        return {
            "runtime": cls.runtime_health(),
            "scheduler": cls.scheduler_status(),
            "jobs": cls.job_metrics(),
            "alerts": cls.alert_metrics(),
            "telemetry": cls.scheduler_telemetry(),
            "timeline": cls.runtime_timeline(),
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
        latest_states = qs.order_by(f"-{order_field}")[:10] if order_field else qs.order_by("-pk")[:10]

        return {
            "total": qs.count(),
            "enabled": enabled,
            "disabled": disabled,
            "latest_states": latest_states,
            "order_field": order_field,
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

        order_field = date_field or cls._first_existing_field(JobExecution, ("id", "pk"))
        latest_jobs_qs = qs.order_by(f"-{order_field}")[:10] if order_field else qs.order_by("-pk")[:10]

        success_rate = round((success_today / total_today) * 100, 2) if total_today else 0

        return {
            "total_today": total_today,
            "success_today": success_today,
            "failed_today": failed_today,
            "running": running,
            "success_rate": success_rate,
            "avg_duration": avg_duration,
            "latest_jobs": list(latest_jobs_qs),
            "latest_jobs_display": cls._build_job_display_rows(latest_jobs_qs),
            "name_field": cls._first_existing_field(JobExecution, cls.JOB_NAME_FIELDS),
            "date_field": date_field,
            "duration_field": duration_field,
        }

    @classmethod
    def alert_metrics(cls):
        active = cls._active_alerts_qs()
        order_field = cls._first_existing_field(RuntimeAlert, cls.ALERT_CREATED_FIELDS)
        latest_alerts_qs = RuntimeAlert.objects.all()

        if order_field:
            latest_alerts_qs = latest_alerts_qs.order_by(f"-{order_field}")[:10]
        else:
            latest_alerts_qs = latest_alerts_qs.order_by("-pk")[:10]

        level_field = cls._first_existing_field(RuntimeAlert, cls.ALERT_LEVEL_FIELDS)
        if level_field:
            by_level = list(
                active.values(level_field)
                .annotate(total=Count("id"))
                .order_by(level_field)
            )
        else:
            by_level = []

        return {
            "active_total": active.count(),
            "by_level": by_level,
            "latest_alerts": list(latest_alerts_qs),
            "latest_alerts_display": cls._build_alert_display_rows(latest_alerts_qs),
            "level_field": level_field,
            "message_field": cls._first_existing_field(RuntimeAlert, cls.ALERT_MESSAGE_FIELDS),
            "date_field": order_field,
        }


    @classmethod
    def scheduler_telemetry(cls):
        """
        Runtime telemetry focused on scheduler freshness.
        Read-only and field-tolerant.
        """
        qs = SchedulerState.objects.all()
        heartbeat_field = cls._first_existing_field(
            SchedulerState,
            ("heartbeat", "last_heartbeat", "updated_at", "atualizado_em", "last_run_at"),
        )
        next_run_field = cls._first_existing_field(
            SchedulerState,
            ("next_run_at", "proxima_execucao", "scheduled_for"),
        )
        status_field = cls._first_existing_field(
            SchedulerState,
            ("last_status", "status", "estado"),
        )

        now = timezone.now()
        stale_threshold = now - timezone.timedelta(minutes=15)

        stale_count = 0
        latest_heartbeat = None
        next_run_at = None
        rows = []

        order_field = heartbeat_field or next_run_field or "pk"
        states = qs.order_by(f"-{order_field}")[:10] if order_field != "pk" else qs.order_by("-pk")[:10]

        for state in states:
            heartbeat = cls._value(state, heartbeat_field)
            next_run = cls._value(state, next_run_field)
            status = cls._value(state, status_field, default="—")

            is_stale = False
            if heartbeat and hasattr(heartbeat, "tzinfo"):
                is_stale = heartbeat < stale_threshold
                if latest_heartbeat is None or heartbeat > latest_heartbeat:
                    latest_heartbeat = heartbeat

            if next_run and hasattr(next_run, "tzinfo"):
                if next_run_at is None or next_run < next_run_at:
                    next_run_at = next_run

            if is_stale:
                stale_count += 1

            rows.append(
                {
                    "name": cls._value(
                        state,
                        cls._first_existing_field(SchedulerState, ("job_name", "name", "nome", "codigo", "code")),
                        default=f"Scheduler #{state.pk}",
                    ),
                    "status": status,
                    "heartbeat": heartbeat or "—",
                    "next_run_at": next_run or "—",
                    "is_stale": is_stale,
                    "object": state,
                }
            )

        lag_seconds = None
        if latest_heartbeat:
            lag_seconds = int((now - latest_heartbeat).total_seconds())

        return {
            "heartbeat_field": heartbeat_field,
            "next_run_field": next_run_field,
            "status_field": status_field,
            "latest_heartbeat": latest_heartbeat,
            "next_run_at": next_run_at,
            "lag_seconds": lag_seconds,
            "stale_count": stale_count,
            "rows": rows,
        }

    @classmethod
    def runtime_timeline(cls, limit=15):
        """
        Consolidated operational feed with recent jobs and runtime alerts.
        This is intentionally read-only and small for SQLite/dev safety.
        """
        events = []

        jobs = cls.job_metrics().get("latest_jobs_display", [])[:limit]
        for job in jobs:
            status = str(job.get("status") or "—")
            events.append(
                {
                    "kind": "job",
                    "severity": cls._severity_from_status(status),
                    "title": job.get("name") or "Job",
                    "description": f"Status: {status}",
                    "timestamp": job.get("created_at"),
                }
            )

        alerts = cls.alert_metrics().get("latest_alerts_display", [])[:limit]
        for alert in alerts:
            level = str(alert.get("level") or "warning")
            events.append(
                {
                    "kind": "alert",
                    "severity": cls._normalize_severity(level),
                    "title": f"Runtime alert · {level}",
                    "description": alert.get("message") or "—",
                    "timestamp": alert.get("created_at"),
                }
            )

        def sort_key(event):
            value = event.get("timestamp")
            return value if hasattr(value, "isoformat") else timezone.datetime.min.replace(tzinfo=timezone.get_current_timezone())

        events.sort(key=sort_key, reverse=True)
        return events[:limit]

    @classmethod
    def _severity_from_status(cls, status):
        status = str(status or "").lower()

        if status in cls.JOB_FAILED_STATUSES or "erro" in status or "fail" in status:
            return "critical"

        if status in cls.JOB_RUNNING_STATUSES or "running" in status or "execut" in status:
            return "info"

        if status in cls.JOB_SUCCESS_STATUSES or "success" in status or "ok" in status:
            return "success"

        return "warning"

    @staticmethod
    def _normalize_severity(value):
        value = str(value or "").lower()

        if value in {"critical", "critico", "crítico", "error", "erro", "fatal"}:
            return "critical"

        if value in {"warning", "warn", "aviso", "alerta"}:
            return "warning"

        if value in {"success", "ok", "healthy", "resolved"}:
            return "success"

        return "info"


    @classmethod
    def global_kpis(cls):
        return {
            "total_jobs": JobExecution.objects.count(),
            "total_scheduler_states": SchedulerState.objects.count(),
            "total_alerts": RuntimeAlert.objects.count(),
            "active_alerts": cls._active_alerts_qs().count(),
            "scheduler_stale": cls.scheduler_telemetry().get("stale_count", 0),
        }

    @classmethod
    def _build_job_display_rows(cls, jobs):
        name_field = cls._first_existing_field(JobExecution, cls.JOB_NAME_FIELDS)
        date_field = cls._first_existing_field(JobExecution, cls.DATE_FIELDS)
        duration_field = cls._first_existing_field(JobExecution, cls.DURATION_FIELDS)

        rows = []
        for job in jobs:
            rows.append(
                {
                    "name": cls._value(job, name_field, default=f"Job #{job.pk}"),
                    "status": cls._value(job, "status", default="—"),
                    "duration": cls._value(job, duration_field, default="—"),
                    "created_at": cls._value(job, date_field, default="—"),
                    "object": job,
                }
            )
        return rows

    @classmethod
    def _build_alert_display_rows(cls, alerts):
        level_field = cls._first_existing_field(RuntimeAlert, cls.ALERT_LEVEL_FIELDS)
        message_field = cls._first_existing_field(RuntimeAlert, cls.ALERT_MESSAGE_FIELDS)
        date_field = cls._first_existing_field(RuntimeAlert, cls.ALERT_CREATED_FIELDS)

        rows = []
        for alert in alerts:
            rows.append(
                {
                    "level": cls._value(alert, level_field, default="—"),
                    "message": cls._value(alert, message_field, default="—"),
                    "created_at": cls._value(alert, date_field, default="—"),
                    "object": alert,
                }
            )
        return rows

    @classmethod
    def _jobs_by_status(cls, statuses):
        return cls._filter_by_status(JobExecution.objects.all(), statuses)

    @classmethod
    def _filter_by_status(cls, qs, statuses):
        if not cls._has_field(qs.model, "status"):
            return qs.none()

        status_filter = Q()
        for status in statuses:
            status_filter |= Q(status__iexact=status)

        return qs.filter(status_filter)

    @classmethod
    def _active_alerts_qs(cls):
        qs = RuntimeAlert.objects.all()

        for field_name in cls.ALERT_RESOLVED_FIELDS:
            if cls._has_field(RuntimeAlert, field_name):
                return qs.filter(**{field_name: False})

        return qs

    @classmethod
    def _stale_scheduler_states_count(cls):
        stale_filter = Q()

        if cls._has_field(SchedulerState, "last_status"):
            stale_filter |= Q(last_status__icontains="stale")

        if cls._has_field(SchedulerState, "runtime_notes"):
            stale_filter |= Q(runtime_notes__icontains="stale")

        if not stale_filter:
            return 0

        return SchedulerState.objects.filter(stale_filter).count()

    @staticmethod
    def _has_field(model, field_name):
        if not field_name:
            return False
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

    @staticmethod
    def _value(obj, field_name, default=None):
        if not field_name:
            return default

        value = getattr(obj, field_name, default)
        if value is None or value == "":
            return default

        return value
