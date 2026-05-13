from django.utils import timezone

from apps.automacoes.models import JobExecution, SchedulerState
from apps.automacoes.services.scheduler_heartbeat import obter_runtime_health


def obter_scheduler_monitoring(limit=20):
    agora = timezone.now()

    states = SchedulerState.objects.order_by("job_name")

    vencidos = states.filter(
        enabled=True,
        next_run_at__isnull=False,
        next_run_at__lte=agora,
    )

    stale = states.filter(
        enabled=True,
        heartbeat_at__lt=agora - timezone.timedelta(minutes=30),
    )

    recentes = JobExecution.objects.order_by("-created_at")[:limit]

    proximos = states.filter(
        enabled=True,
        next_run_at__isnull=False,
    ).order_by("next_run_at")[:limit]

    return {
        "runtime_health": obter_runtime_health(),
        "states": states,
        "vencidos": vencidos,
        "stale": stale,
        "recentes": recentes,
        "proximos": proximos,
        "agora": agora,
    }
