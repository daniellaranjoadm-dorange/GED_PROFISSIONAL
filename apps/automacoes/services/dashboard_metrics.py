"""
Métricas centralizadas para dashboards do módulo de automações.

Este service reduz a responsabilidade do views.py e concentra KPIs
reutilizáveis para telas, APIs, relatórios e BI futuro.
"""

from django.db.models import Q

from apps.automacoes.models import DocumentoLD, KMFileIndex, PCFTimeline, TransmittalKM
from apps.automacoes.services.status_normalizer import normalizar_status


def _model_has_field(model, nome):
    """Retorna True quando o model possui o campo informado."""
    return any(field.name == nome for field in model._meta.get_fields())


def obter_kpis_ld():
    """KPIs principais da Lista de Documentos."""
    total_ld = DocumentoLD.objects.count()

    total_ld_com_pcf = 0
    if _model_has_field(DocumentoLD, "pcf"):
        total_ld_com_pcf = (
            DocumentoLD.objects.exclude(pcf="")
            .exclude(pcf__isnull=True)
            .count()
        )

    total_ld_sem_pcf = max(total_ld - total_ld_com_pcf, 0)

    return {
        "total_ld": total_ld,
        "total_ld_com_pcf": total_ld_com_pcf,
        "total_ld_sem_pcf": total_ld_sem_pcf,
    }


def obter_kpis_pcfs():
    """
    KPIs principais de PCFs.

    A contagem por status usa normalização em memória para consolidar:
    Released, released, RELEASED etc.
    """
    total_pcfs = PCFTimeline.objects.count()

    total_pcfs_open = 0
    if _model_has_field(PCFTimeline, "open_comments"):
        total_pcfs_open = PCFTimeline.objects.filter(open_comments__gt=0).count()

    status_normalizados = []
    if _model_has_field(PCFTimeline, "status_final"):
        status_normalizados = [
            normalizar_status(status)
            for status in PCFTimeline.objects.values_list("status_final", flat=True)
        ]

    total_pcfs_released = status_normalizados.count("RELEASED")
    total_pcfs_not_released = status_normalizados.count("NOT RELEASED")
    total_pcfs_released_with_comments = status_normalizados.count("RELEASED WITH COMMENTS")

    return {
        "total_pcfs": total_pcfs,
        "total_pcfs_open": total_pcfs_open,
        "total_pcfs_released": total_pcfs_released,
        "total_pcfs_not_released": total_pcfs_not_released,
        "total_pcfs_released_with_comments": total_pcfs_released_with_comments,
    }


def obter_kpis_transmittals():
    """KPIs principais de Transmittals KM importados."""
    total_transmittals = TransmittalKM.objects.count()

    total_transmittals_unicos = 0
    if _model_has_field(TransmittalKM, "transmittal_numero"):
        total_transmittals_unicos = (
            TransmittalKM.objects.exclude(transmittal_numero="")
            .exclude(transmittal_numero__isnull=True)
            .values("transmittal_numero")
            .distinct()
            .count()
        )

    total_transmittals_sem_pdf = 0
    if _model_has_field(TransmittalKM, "arquivo_pdf"):
        total_transmittals_sem_pdf = (
            TransmittalKM.objects.filter(Q(arquivo_pdf="") | Q(arquivo_pdf__isnull=True))
            .count()
        )

    return {
        "total_transmittals": total_transmittals,
        "total_transmittals_unicos": total_transmittals_unicos,
        "total_transmittals_sem_pdf": total_transmittals_sem_pdf,
    }


def obter_kpis_km_index():
    """KPIs principais do índice persistente KM."""
    total_km_index = KMFileIndex.objects.filter(ativo=True).count()
    total_km_docs_index = KMFileIndex.objects.filter(
        ativo=True,
        eh_transmittal_letter=False,
    ).count()
    total_km_transmittals_index = KMFileIndex.objects.filter(
        ativo=True,
        eh_transmittal_letter=True,
    ).count()

    ultima_indexacao_km = (
        KMFileIndex.objects.filter(ativo=True)
        .order_by("-indexado_em")
        .values_list("indexado_em", flat=True)
        .first()
    )

    return {
        "total_km_index": total_km_index,
        "total_km_docs_index": total_km_docs_index,
        "total_km_transmittals_index": total_km_transmittals_index,
        "ultima_indexacao_km": ultima_indexacao_km,
    }


def obter_kpis_dashboard():
    """
    Agrega os principais KPIs usados no painel enterprise.

    Mantém uma única chamada para facilitar uso em views, APIs e relatórios.
    """
    return {
        **obter_kpis_ld(),
        **obter_kpis_pcfs(),
        **obter_kpis_transmittals(),
        **obter_kpis_km_index(),
    }
