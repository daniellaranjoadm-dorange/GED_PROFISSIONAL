from django.utils import timezone

from apps.automacoes.models import JobExecution, SchedulerState
from apps.automacoes.services.scheduler_policies import obter_policy


def obter_ou_criar_scheduler_state(job_name: str) -> SchedulerState:
    state, _ = SchedulerState.objects.get_or_create(
        job_name=job_name,
        defaults={
            "last_status": SchedulerState.STATUS_IDLE,
            "enabled": True,
        },
    )
    return state


def calcular_proxima_execucao(job_name: str, base=None):
    policy = obter_policy(job_name)
    base = base or timezone.now()
    return base + timezone.timedelta(minutes=policy.interval_minutes)


def registrar_inicio_job(job_name: str) -> SchedulerState:
    agora = timezone.now()
    state = obter_ou_criar_scheduler_state(job_name)
    state.last_run_at = agora
    state.heartbeat_at = agora
    state.last_status = SchedulerState.STATUS_RUNNING
    state.runtime_notes = "Execução iniciada."
    state.save(
        update_fields=[
            "last_run_at",
            "heartbeat_at",
            "last_status",
            "runtime_notes",
            "updated_at",
        ]
    )
    return state


def registrar_fim_job(job: JobExecution) -> SchedulerState:
    agora = timezone.now()
    state = obter_ou_criar_scheduler_state(job.job_name)

    state.heartbeat_at = agora
    state.next_run_at = calcular_proxima_execucao(job.job_name, base=agora)

    if job.status == JobExecution.STATUS_SUCCESS:
        state.last_status = SchedulerState.STATUS_SUCCESS
        state.last_success_at = agora
        state.runtime_notes = "Última execução concluída com sucesso."
        update_fields = [
            "heartbeat_at",
            "next_run_at",
            "last_status",
            "last_success_at",
            "runtime_notes",
            "updated_at",
        ]
    elif job.status == JobExecution.STATUS_FAILED:
        state.last_status = SchedulerState.STATUS_FAILED
        state.last_failure_at = agora
        state.runtime_notes = job.error or "Última execução falhou."
        update_fields = [
            "heartbeat_at",
            "next_run_at",
            "last_status",
            "last_failure_at",
            "runtime_notes",
            "updated_at",
        ]
    else:
        state.last_status = job.status
        state.runtime_notes = "Execução finalizada com status não terminal."
        update_fields = [
            "heartbeat_at",
            "next_run_at",
            "last_status",
            "runtime_notes",
            "updated_at",
        ]

    state.save(update_fields=update_fields)
    return state


def sincronizar_state_com_jobs_registrados(job_names):
    states = []
    for job_name in job_names:
        state = obter_ou_criar_scheduler_state(job_name)
        if not state.next_run_at:
            state.next_run_at = calcular_proxima_execucao(job_name)
            state.save(update_fields=["next_run_at", "updated_at"])
        states.append(state)
    return states
