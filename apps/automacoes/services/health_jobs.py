from django.utils import timezone

from apps.automacoes.models import DocumentoLD, KMFileIndex, PCFTimeline, TransmittalKM
from apps.automacoes.services.scheduler import ScheduledJob, registrar_job_agendado


def executar_health_scan():
    """
    Health scan leve e síncrono.

    Não varre rede.
    Não abre arquivos.
    Não executa automações pesadas.

    Apenas consolida indicadores básicos para provar a fundação do scheduler.
    """

    return {
        "ok": True,
        "mensagem": "Health scan executado com sucesso.",
        "executado_em": timezone.now().isoformat(),
        "metricas": {
            "documentos_ld": DocumentoLD.objects.count(),
            "pcfs": PCFTimeline.objects.count(),
            "transmittals_km": TransmittalKM.objects.count(),
            "km_index_ativo": KMFileIndex.objects.filter(ativo=True).count(),
        },
    }


def registrar_health_jobs():
    return registrar_job_agendado(
        ScheduledJob(
            name="health_scan",
            description="Executa health scan leve do GED.",
            handler=executar_health_scan,
            enabled=True,
        )
    )
