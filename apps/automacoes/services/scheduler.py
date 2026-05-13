from dataclasses import dataclass
from typing import Callable, Dict, Iterable, Optional

from apps.automacoes.models import JobExecution
from apps.automacoes.services.job_manager import executar_job_sincrono


@dataclass(frozen=True)
class ScheduledJob:
    """
    Contrato simples para jobs agendáveis.

    Esta camada ainda não agenda por tempo real.
    Ela centraliza o catálogo de jobs para permitir, no futuro:
    - scheduler interno
    - management command
    - Celery Beat
    - Windows Task Scheduler
    - GitHub Actions
    """

    name: str
    description: str
    handler: Callable
    enabled: bool = True


_REGISTRY: Dict[str, ScheduledJob] = {}


def registrar_job_agendado(job: ScheduledJob):
    if not job.name:
        raise ValueError("ScheduledJob.name é obrigatório.")

    _REGISTRY[job.name] = job
    return job


def listar_jobs_agendados(include_disabled: bool = False) -> Iterable[ScheduledJob]:
    jobs = list(_REGISTRY.values())

    if include_disabled:
        return jobs

    return [job for job in jobs if job.enabled]


def obter_job_agendado(name: str) -> Optional[ScheduledJob]:
    return _REGISTRY.get(name)


def executar_job_agendado(name: str, payload=None, user=None) -> JobExecution:
    job = obter_job_agendado(name)

    if not job:
        raise ValueError(f"Job agendado não registrado: {name}")

    if not job.enabled:
        raise ValueError(f"Job agendado desabilitado: {name}")

    return executar_job_sincrono(
        job_name=job.name,
        func=job.handler,
        payload=payload or {},
        user=user,
    )


def limpar_registry_jobs_agendados():
    """
    Uso principal: testes.
    Evita estado global contaminando a suíte.
    """

    _REGISTRY.clear()
