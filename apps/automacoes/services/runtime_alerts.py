from django.utils import timezone

from apps.automacoes.models import RuntimeAlert, SchedulerState


def alerta_aberto_existe(codigo: str, job_name: str = "") -> bool:
    return RuntimeAlert.objects.filter(
        codigo=codigo,
        job_name=job_name or "",
        resolvido=False,
    ).exists()


def criar_alerta_runtime(
    codigo,
    titulo,
    mensagem,
    severidade=RuntimeAlert.SEVERITY_WARNING,
    job_name="",
    detalhes=None,
    deduplicar=True,
):
    if deduplicar and alerta_aberto_existe(codigo, job_name):
        return None

    return RuntimeAlert.objects.create(
        codigo=codigo,
        titulo=titulo,
        mensagem=mensagem,
        severidade=severidade,
        job_name=job_name or "",
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
            detalhes={
                "heartbeat_at": state.heartbeat_at.isoformat() if state.heartbeat_at else None,
                "minutos_limite": minutos,
            },
        )
        if alerta:
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
            detalhes={
                "last_failure_at": state.last_failure_at.isoformat() if state.last_failure_at else None,
                "runtime_notes": state.runtime_notes,
            },
        )
        if alerta:
            alertas.append(alerta)

    return alertas


def executar_varredura_alertas_runtime():
    alertas = []
    alertas.extend(detectar_scheduler_stale())
    alertas.extend(detectar_jobs_falhando())

    return {
        "ok": True,
        "alertas_criados": len(alertas),
        "codigos": [alerta.codigo for alerta in alertas],
    }
