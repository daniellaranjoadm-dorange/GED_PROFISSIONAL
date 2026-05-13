# Patch cirúrgico opcional em apps/automacoes/services/scheduler_runtime.py

# 1) Adicione os imports:
from apps.automacoes.services.scheduler_state import registrar_fim_job, registrar_inicio_job


# 2) Substitua executar_job_agendado_com_lock por esta versão:
def executar_job_agendado_com_lock(name: str, payload=None, user=None):
    with job_runtime_lock(name):
        registrar_inicio_job(name)
        job = executar_job_agendado(
            name=name,
            payload=payload or {},
            user=user,
        )
        registrar_fim_job(job)
        return job
