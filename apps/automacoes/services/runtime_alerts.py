
from django.utils import timezone

from apps.automacoes.models import RuntimeAlert, SchedulerState


def criar_alerta_runtime(
    codigo,
    titulo,
    mensagem,
    severidade=RuntimeAlert.SEVERITY_WARNING,
    job_name="",
    detalhes=None,
):
    return RuntimeAlert.objects.create(
        codigo=codigo,
        titulo=titulo,
        mensagem=mensagem,
        severidade=severidade,
        job_name=job_name,
        detalhes=detalhes or {},
    )


def detectar_scheduler_stale(minutos=30):
    limite = timezone.now() - timezone.timedelta(minutes=minutos)

    stale = SchedulerState.objects.filter(
        enabled=True,
        heartbeat_at__lt=limite,
    )

    alertas = []

    for state in stale:
        alerta = criar_alerta_runtime(
            codigo="SCHEDULER_STALE",
            titulo="Scheduler heartbeat obsoleto",
            mensagem=f"Heartbeat antigo detectado para {state.job_name}",
            severidade=RuntimeAlert.SEVERITY_ERROR,
            job_name=state.job_name,
        )
        alertas.append(alerta)

    return alertas


def detectar_jobs_falhando():
    failed = SchedulerState.objects.filter(
        enabled=True,
        last_status=SchedulerState.STATUS_FAILED,
    )

    alertas = []

    for state in failed:
        alerta = criar_alerta_runtime(
            codigo="JOB_FAILED",
            titulo="Job falhando",
            mensagem=f"Última execução falhou para {state.job_name}",
            severidade=RuntimeAlert.SEVERITY_WARNING,
            job_name=state.job_name,
        )
        alertas.append(alerta)

    return alertas
