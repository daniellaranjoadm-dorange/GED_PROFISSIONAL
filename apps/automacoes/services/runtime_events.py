from dataclasses import dataclass
from typing import Any

from django.utils import timezone

from apps.automacoes.models import JobExecution, RuntimeAlert, SchedulerState


@dataclass(frozen=True)
class RuntimeEvent:
    timestamp: Any
    source: str
    title: str
    message: str
    severity: str
    badge: str
    object_id: Any = None


class RuntimeEventStreamService:
    """
    Read-only event stream for the Operations Center.

    Consolidates scheduler, job and alert signals into one operational feed.
    Defensive with field names because runtime models evolved over multiple sprints.
    """

    JOB_SUCCESS_STATUSES = ("success", "sucesso", "completed", "done", "ok")
    JOB_FAILED_STATUSES = ("failed", "failure", "erro", "error")
    JOB_RUNNING_STATUSES = ("running", "iniciado", "processing", "started")

    JOB_NAME_FIELDS = ("job_name", "name", "nome", "task_name")
    JOB_CREATED_FIELDS = ("created_at", "criado_em", "started_at", "iniciado_em")
    JOB_MESSAGE_FIELDS = ("message", "mensagem", "error", "erro", "runtime_notes")

    ALERT_CREATED_FIELDS = ("created_at", "criado_em", "timestamp")
    ALERT_LEVEL_FIELDS = ("level", "severity", "nivel")
    ALERT_MESSAGE_FIELDS = ("message", "mensagem", "description", "descricao")
    ALERT_CODE_FIELDS = ("code", "codigo", "alert_code", "tipo")

    SCHEDULER_NAME_FIELDS = ("job_name", "name", "nome", "task_name", "codigo")
    SCHEDULER_STATUS_FIELDS = ("last_status", "status")
    SCHEDULER_NOTE_FIELDS = ("runtime_notes", "notes", "observacao")
    SCHEDULER_TIME_FIELDS = ("updated_at", "atualizado_em", "heartbeat", "last_heartbeat")

    @classmethod
    def build_stream(cls, limit=30):
        events = []
        events.extend(cls._job_events(limit=limit))
        events.extend(cls._alert_events(limit=limit))
        events.extend(cls._scheduler_events(limit=limit))

        fallback_min = timezone.make_aware(timezone.datetime.min)
        events.sort(key=lambda event: event.timestamp or fallback_min, reverse=True)
        return events[:limit]

    @classmethod
    def summary(cls):
        events = cls.build_stream(limit=50)
        return {
            "total": len(events),
            "critical": sum(1 for event in events if event.severity == "CRITICAL"),
            "error": sum(1 for event in events if event.severity == "ERROR"),
            "warning": sum(1 for event in events if event.severity == "WARNING"),
            "info": sum(1 for event in events if event.severity == "INFO"),
            "updated_at": timezone.now(),
        }

    @classmethod
    def _job_events(cls, limit=10):
        date_field = cls._first_existing_field(JobExecution, cls.JOB_CREATED_FIELDS)
        qs = JobExecution.objects.all()
        qs = qs.order_by(f"-{date_field}")[:limit] if date_field else qs.order_by("-id")[:limit]

        events = []
        for job in qs:
            status = str(cls._value(job, "status", default="")).lower()
            name = cls._first_value(job, cls.JOB_NAME_FIELDS, default=f"Job #{job.pk}")
            timestamp = cls._first_value(job, cls.JOB_CREATED_FIELDS)
            message = cls._first_value(job, cls.JOB_MESSAGE_FIELDS, default=f"Status: {status or 'unknown'}")

            severity = cls._severity_from_job_status(status)
            badge = "job-success" if severity == "INFO" else "job-warning"
            if severity in ("ERROR", "CRITICAL"):
                badge = "job-error"
            elif status in cls.JOB_RUNNING_STATUSES:
                badge = "job-running"

            events.append(RuntimeEvent(timestamp, "JOB", str(name), str(message or ""), severity, badge, job.pk))

        return events

    @classmethod
    def _alert_events(cls, limit=10):
        date_field = cls._first_existing_field(RuntimeAlert, cls.ALERT_CREATED_FIELDS)
        qs = RuntimeAlert.objects.all()
        qs = qs.order_by(f"-{date_field}")[:limit] if date_field else qs.order_by("-id")[:limit]

        events = []
        for alert in qs:
            raw_level = cls._first_value(alert, cls.ALERT_LEVEL_FIELDS, default="warning")
            message = cls._first_value(alert, cls.ALERT_MESSAGE_FIELDS, default="Runtime alert")
            code = cls._first_value(alert, cls.ALERT_CODE_FIELDS, default="Runtime Alert")
            timestamp = cls._first_value(alert, cls.ALERT_CREATED_FIELDS)
            severity = cls._normalize_severity(raw_level)

            events.append(RuntimeEvent(timestamp, "ALERT", str(code or "Runtime Alert"), str(message or ""), severity, f"alert-{severity.lower()}", alert.pk))

        return events

    @classmethod
    def _scheduler_events(cls, limit=10):
        date_field = cls._first_existing_field(SchedulerState, cls.SCHEDULER_TIME_FIELDS)
        qs = SchedulerState.objects.all()
        qs = qs.order_by(f"-{date_field}")[:limit] if date_field else qs.order_by("-id")[:limit]

        events = []
        for state in qs:
            name = cls._first_value(state, cls.SCHEDULER_NAME_FIELDS, default=f"Scheduler #{state.pk}")
            status = cls._first_value(state, cls.SCHEDULER_STATUS_FIELDS, default="unknown")
            notes = cls._first_value(state, cls.SCHEDULER_NOTE_FIELDS, default="")
            timestamp = cls._first_value(state, cls.SCHEDULER_TIME_FIELDS)
            severity = cls._severity_from_scheduler_status(status, notes)

            events.append(RuntimeEvent(timestamp, "SCHEDULER", str(name), str(notes or f"Status: {status or 'unknown'}"), severity, f"scheduler-{severity.lower()}", state.pk))

        return events

    @classmethod
    def _severity_from_job_status(cls, status):
        status = str(status or "").lower()
        if status in cls.JOB_FAILED_STATUSES:
            return "ERROR"
        if status in cls.JOB_RUNNING_STATUSES:
            return "WARNING"
        return "INFO"

    @classmethod
    def _severity_from_scheduler_status(cls, status, notes=""):
        text = f"{status or ''} {notes or ''}".lower()
        if "critical" in text or "critico" in text or "crítico" in text:
            return "CRITICAL"
        if "fail" in text or "error" in text or "erro" in text:
            return "ERROR"
        if "stale" in text or "warning" in text or "warn" in text:
            return "WARNING"
        return "INFO"

    @classmethod
    def _normalize_severity(cls, value):
        text = str(value or "").strip().lower()
        if text in {"critical", "critico", "crítico", "fatal"}:
            return "CRITICAL"
        if text in {"error", "erro", "failed", "failure"}:
            return "ERROR"
        if text in {"warning", "warn", "aviso", "alerta"}:
            return "WARNING"
        return "INFO"

    @staticmethod
    def _has_field(model, field_name):
        return any(field.name == field_name for field in model._meta.get_fields())

    @classmethod
    def _first_existing_field(cls, model, field_names):
        for field_name in field_names:
            if cls._has_field(model, field_name):
                return field_name
        return None

    @staticmethod
    def _value(obj, field_name, default=None):
        try:
            return getattr(obj, field_name)
        except Exception:
            return default

    @classmethod
    def _first_value(cls, obj, field_names, default=None):
        for field_name in field_names:
            if hasattr(obj, field_name):
                value = cls._value(obj, field_name)
                if value not in (None, ""):
                    return value
        return default
