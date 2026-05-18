from apps.automacoes.services.km_index_jobs import executar_reindexacao_km_job
from apps.automacoes.services.km_ld_sync_engine import executar_sync_km_ld_job
from apps.automacoes.services.scheduler import ScheduledJob, registrar_job_agendado


def registrar_km_jobs():
    job_reindex = registrar_job_agendado(
        ScheduledJob(
            name="km_reindex",
            description="Executa reindexação KM como job gerenciado.",
            handler=executar_reindexacao_km_job,
            enabled=True,
        )
    )

    registrar_job_agendado(
        ScheduledJob(
            name="km_ld_sync",
            description="Executa sincronização inteligente KM ↔ LD.",
            handler=executar_sync_km_ld_job,
            enabled=True,
        )
    )

    return job_reindex
