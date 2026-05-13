from django.utils import timezone

from apps.automacoes.models import SchedulerState
from apps.automacoes.services.scheduler_state import obter_ou_criar_scheduler_state


def registrar_heartbeat(job_name: str, note: str = "") -> SchedulerState:
    state = obter_ou_criar_scheduler_state(job_name)
    state.heartbeat_at = timezone.now()

    if note:
        state.runtime_notes = note
        state.save(update_fields=["heartbeat_at", "runtime_notes", "updated_at"])
    else:
        state.save(update_fields=["heartbeat_at", "updated_at"])

    return state


def scheduler_state_esta_obsoleto(state: SchedulerState, minutos: int = 30) -> bool:
    if not state.heartbeat_at:
        return True

    limite = timezone.now() - timezone.timedelta(minutes=minutos)
    return state.heartbeat_at < limite


def listar_states_obsoletos(minutos: int = 30):
    limite = timezone.now() - timezone.timedelta(minutes=minutos)
    return SchedulerState.objects.filter(
        heartbeat_at__lt=limite,
        enabled=True,
    )


def obter_runtime_health(minutos_obsoleto: int = 30):
    total = SchedulerState.objects.count()
    enabled = SchedulerState.objects.filter(enabled=True).count()
    running = SchedulerState.objects.filter(
        last_status=SchedulerState.STATUS_RUNNING,
        enabled=True,
    ).count()
    failed = SchedulerState.objects.filter(
        last_status=SchedulerState.STATUS_FAILED,
        enabled=True,
    ).count()
    stale = listar_states_obsoletos(minutos=minutos_obsoleto).count()

    return {
        "total": total,
        "enabled": enabled,
        "running": running,
        "failed": failed,
        "stale": stale,
        "healthy": failed == 0 and stale == 0,
    }
