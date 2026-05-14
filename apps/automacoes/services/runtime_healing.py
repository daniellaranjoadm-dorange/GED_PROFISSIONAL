from django.utils import timezone

from apps.automacoes.models import JobExecution, RuntimeAlert, SchedulerState
from apps.automacoes.services.runtime_alerts import criar_alerta_runtime
from apps.automacoes.services.scheduler_policies import obter_policy
from apps.automacoes.services.scheduler_state import calcular_proxima_execucao


def recuperar_jobs_running_presos(minutos=None):
    """
    Marca jobs RUNNING antigos como FAILED.

    Esta rotina não reexecuta automaticamente.
    Apenas libera o runtime e registra alerta.
    """

    agora = timezone.now()
    total = 0
    recuperados = []

    qs = JobExecution.objects.filter(
        status=JobExecution.STATUS_RUNNING,
        started_at__isnull=False,
    )

    for job in qs:
        policy = obter_policy(job.job_name)
        limite_minutos = minutos or policy.timeout_minutes
        limite = agora - timezone.timedelta(minutes=limite_minutos)

        if job.started_at >= limite:
            continue

        job.status = JobExecution.STATUS_FAILED
        job.finished_at = agora
        job.error = "Job recuperado automaticamente por timeout operacional."
        job.duration_ms = int((agora - job.started_at).total_seconds() * 1000)
        job.save(
            update_fields=[
                "status",
                "finished_at",
                "error",
                "duration_ms",
                "updated_at",
            ]
        )

        criar_alerta_runtime(
            codigo="JOB_TIMEOUT_RECOVERED",
            titulo="Job preso recuperado",
            mensagem=f"Job {job.job_name} foi marcado como FAILED após timeout.",
            severidade=RuntimeAlert.SEVERITY_ERROR,
            job_name=job.job_name,
            detalhes={
                "job_id": job.id,
                "timeout_minutes": limite_minutos,
            },
        )

        total += 1
        recuperados.append(job.id)

    return {
        "ok": True,
        "total": total,
        "job_ids": recuperados,
    }


def recuperar_scheduler_states_stale(minutos=60):
    """
    Atualiza states com heartbeat obsoleto para permitir nova tentativa futura.

    Não desabilita o job.
    Não executa o job.
    Apenas marca estado como FAILED e recalcula next_run_at.
    """

    agora = timezone.now()
    limite = agora - timezone.timedelta(minutes=minutos)

    qs = SchedulerState.objects.filter(
        enabled=True,
        heartbeat_at__isnull=False,
        heartbeat_at__lt=limite,
    )

    total = 0
    nomes = []

    for state in qs:
        state.last_status = SchedulerState.STATUS_FAILED
        state.last_failure_at = agora
        state.next_run_at = calcular_proxima_execucao(state.job_name, base=agora)
        state.runtime_notes = "Scheduler state recuperado automaticamente por heartbeat stale."
        state.save(
            update_fields=[
                "last_status",
                "last_failure_at",
                "next_run_at",
                "runtime_notes",
                "updated_at",
            ]
        )

        criar_alerta_runtime(
            codigo="SCHEDULER_STATE_RECOVERED",
            titulo="Scheduler state recuperado",
            mensagem=f"State {state.job_name} recuperado por heartbeat stale.",
            severidade=RuntimeAlert.SEVERITY_WARNING,
            job_name=state.job_name,
            detalhes={
                "heartbeat_at": state.heartbeat_at.isoformat() if state.heartbeat_at else None,
                "minutos": minutos,
            },
        )

        total += 1
        nomes.append(state.job_name)

    return {
        "ok": True,
        "total": total,
        "jobs": nomes,
    }


def executar_self_healing_runtime():
    jobs = recuperar_jobs_running_presos()
    states = recuperar_scheduler_states_stale()

    return {
        "ok": jobs["ok"] and states["ok"],
        "jobs_recuperados": jobs["total"],
        "states_recuperados": states["total"],
        "detalhes": {
            "jobs": jobs,
            "states": states,
        },
    }
