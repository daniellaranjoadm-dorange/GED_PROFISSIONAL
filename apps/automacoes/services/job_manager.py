import time
import traceback
from typing import Any, Callable

from django.db import close_old_connections
from django.utils import timezone

from apps.automacoes.models import JobExecution


def criar_job(job_name: str, payload: dict | None = None, user=None) -> JobExecution:
    """
    Registra um job pendente sem executá-lo.

    Esta fundação permite trocar o backend futuramente por Celery/Redis sem
    alterar views ou services consumidores.
    """
    return JobExecution.objects.create(
        job_name=str(job_name or "").strip() or "job_sem_nome",
        status=JobExecution.STATUS_PENDING,
        payload=payload or {},
        created_by=user if getattr(user, "is_authenticated", False) else None,
    )


def executar_job_sincrono(
    job_name: str,
    func: Callable[..., Any],
    payload: dict | None = None,
    user=None,
    *args,
    **kwargs,
) -> JobExecution:
    """
    Executa um job localmente, com rastreabilidade persistente.

    Mantém o processamento síncrono por enquanto, mas já estabelece contrato
    para futura execução assíncrona.
    """
    job = criar_job(job_name=job_name, payload=payload, user=user)
    inicio = time.monotonic()

    job.status = JobExecution.STATUS_RUNNING
    job.started_at = timezone.now()
    job.save(update_fields=["status", "started_at", "updated_at"])

    try:
        resultado = func(*args, **kwargs)

        if isinstance(resultado, dict):
            job.result = resultado
        else:
            job.result = {"resultado": resultado}

        job.status = JobExecution.STATUS_SUCCESS
        job.error = ""

    except Exception as exc:
        job.status = JobExecution.STATUS_FAILED
        job.error = "".join(
            traceback.format_exception_only(type(exc), exc)
        ).strip()
        job.result = {
            "ok": False,
            "erro": str(exc),
        }

    finally:
        job.finished_at = timezone.now()
        job.duration_ms = int((time.monotonic() - inicio) * 1000)
        job.save(
            update_fields=[
                "status",
                "result",
                "error",
                "finished_at",
                "duration_ms",
                "updated_at",
            ]
        )
        close_old_connections()

    return job


def job_executou_com_sucesso(job: JobExecution) -> bool:
    return bool(job and job.status == JobExecution.STATUS_SUCCESS)


def listar_jobs_recentes(limite: int = 20):
    limite = max(1, min(int(limite or 20), 200))
    return JobExecution.objects.order_by("-created_at")[:limite]
