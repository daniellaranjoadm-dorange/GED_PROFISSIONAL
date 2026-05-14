from django.utils import timezone

from apps.automacoes.models import SchedulerState
from apps.automacoes.services.health_jobs import registrar_health_jobs
from apps.automacoes.services.km_scheduler_jobs import registrar_km_jobs
from apps.automacoes.services.runtime_alerts import executar_varredura_alertas_runtime
from apps.automacoes.services.scheduler import obter_job_agendado
from apps.automacoes.services.scheduler_runtime import (
    JobAlreadyRunningError,
    executar_job_agendado_com_lock,
)
from apps.automacoes.services.scheduler_state import (
    calcular_proxima_execucao,
    sincronizar_state_com_jobs_registrados,
)


def registrar_jobs_padrao_scheduler():
    """
    Registra os jobs padrão disponíveis para execução automática.
    Mantém o registry em um ponto único para commands, runtime e testes.
    """

    registrar_health_jobs()
    registrar_km_jobs()


def inicializar_scheduler_states():
    registrar_jobs_padrao_scheduler()

    job_names = [
        job.name
        for job in [
            obter_job_agendado("health_scan"),
            obter_job_agendado("km_reindex"),
        ]
        if job
    ]

    return sincronizar_state_com_jobs_registrados(job_names)


def listar_jobs_vencidos(agora=None):
    agora = agora or timezone.now()

    return SchedulerState.objects.filter(
        enabled=True,
        next_run_at__isnull=False,
        next_run_at__lte=agora,
    ).order_by("next_run_at", "job_name")


def scheduler_tick(limit=10, user=None, detectar_alertas=True):
    """
    Executa um ciclo controlado do scheduler.

    Não cria loop infinito.
    Não cria thread.
    Não agenda por conta própria.

    Ideal para:
    - management command
    - Windows Task Scheduler
    - CRON
    - GitHub Actions
    - futuro daemon controlado
    """

    registrar_jobs_padrao_scheduler()
    inicializar_scheduler_states()

    executados = []
    ignorados = []
    erros = []

    for state in listar_jobs_vencidos()[:limit]:
        job_def = obter_job_agendado(state.job_name)

        if not job_def:
            state.runtime_notes = "Job não encontrado no registry."
            state.next_run_at = calcular_proxima_execucao(state.job_name)
            state.save(update_fields=["runtime_notes", "next_run_at", "updated_at"])
            ignorados.append({"job_name": state.job_name, "motivo": "não registrado"})
            continue

        if not job_def.enabled or not state.enabled:
            state.runtime_notes = "Job desabilitado."
            state.next_run_at = calcular_proxima_execucao(state.job_name)
            state.save(update_fields=["runtime_notes", "next_run_at", "updated_at"])
            ignorados.append({"job_name": state.job_name, "motivo": "desabilitado"})
            continue

        try:
            job = executar_job_agendado_com_lock(
                state.job_name,
                payload={"source": "scheduler_tick"},
                user=user,
            )
            executados.append(
                {
                    "job_name": job.job_name,
                    "status": job.status,
                    "job_id": job.id,
                }
            )
        except JobAlreadyRunningError as exc:
            state.runtime_notes = str(exc)
            state.save(update_fields=["runtime_notes", "updated_at"])
            ignorados.append({"job_name": state.job_name, "motivo": "running"})
        except Exception as exc:
            state.runtime_notes = f"Erro no scheduler_tick: {exc}"
            state.next_run_at = calcular_proxima_execucao(state.job_name)
            state.save(update_fields=["runtime_notes", "next_run_at", "updated_at"])
            erros.append({"job_name": state.job_name, "erro": str(exc)})

    alertas = {"ok": True, "alertas_criados": 0, "codigos": []}
    if detectar_alertas:
        alertas = executar_varredura_alertas_runtime()

    return {
        "ok": not erros,
        "executados": executados,
        "ignorados": ignorados,
        "erros": erros,
        "alertas": alertas,
        "total_executados": len(executados),
        "total_ignorados": len(ignorados),
        "total_erros": len(erros),
        "total_alertas": alertas.get("alertas_criados", 0),
    }
