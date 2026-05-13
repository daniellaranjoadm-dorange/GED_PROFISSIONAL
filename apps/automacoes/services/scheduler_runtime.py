from contextlib import contextmanager

from django.db import transaction
from django.utils import timezone

from apps.automacoes.models import JobExecution
from apps.automacoes.services.scheduler import executar_job_agendado


class JobAlreadyRunningError(RuntimeError):
    """Indica que já existe execução ativa para o job solicitado."""


def existe_job_em_execucao(job_name: str) -> bool:
    return JobExecution.objects.filter(
        job_name=job_name,
        status=JobExecution.STATUS_RUNNING,
    ).exists()


@contextmanager
def job_runtime_lock(job_name: str):
    """
    Lock lógico baseado no banco.

    Esta versão é propositalmente simples e compatível com SQLite/testes.
    Em produção futura pode evoluir para:
    - SELECT FOR UPDATE
    - advisory locks
    - Redis lock
    - Celery singleton
    """

    with transaction.atomic():
        if existe_job_em_execucao(job_name):
            raise JobAlreadyRunningError(
                f"Job já está em execução: {job_name}"
            )

    try:
        yield
    finally:
        # O estado final é gerenciado pelo job_manager.
        pass


def executar_job_agendado_com_lock(name: str, payload=None, user=None):
    with job_runtime_lock(name):
        return executar_job_agendado(
            name=name,
            payload=payload or {},
            user=user,
        )


def marcar_jobs_presos_como_falha(minutos=120):
    """
    Recuperação operacional para jobs que ficaram RUNNING por falha externa.

    Não executa automaticamente ainda.
    Pode ser chamado futuramente por management command/scheduler.
    """

    limite = timezone.now() - timezone.timedelta(minutes=minutos)

    qs = JobExecution.objects.filter(
        status=JobExecution.STATUS_RUNNING,
        started_at__lt=limite,
    )

    total = 0

    for job in qs:
        job.status = JobExecution.STATUS_FAILED
        job.finished_at = timezone.now()
        job.error = "Job marcado como falha por timeout operacional."
        job.save(update_fields=["status", "finished_at", "error", "updated_at"])
        total += 1

    return total
