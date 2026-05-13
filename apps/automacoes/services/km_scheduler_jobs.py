from apps.automacoes.services.km_index_jobs import executar_reindexacao_km_job
from apps.automacoes.services.scheduler import ScheduledJob, registrar_job_agendado


def registrar_km_jobs():
    return registrar_job_agendado(
        ScheduledJob(
            name="km_reindex",
            description="Executa reindexação KM como job gerenciado.",
            handler=executar_reindexacao_km_job,
            enabled=True,
        )
    )
