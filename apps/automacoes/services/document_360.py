"""Read-only persisted relationships for one operational document."""
from django.db.models import Prefetch

from apps.automacoes.models import DocumentoLD, PCFTimeline, PendenciaDocumental, TransmittalKM
from apps.documentos.models import (
    ArquivoDocumento, Documento, DocumentoAprovacao, DocumentoReferenciaExterna,
    DocumentoVersao, DocumentoWorkflowHistorico, LogAuditoria,
)
from .document_center import consulta_central_documentos


def consultar_documento_360(document_id):
    """Return a visible document, or None. Never synchronize or repair links."""
    return (
        consulta_central_documentos()
        .filter(pk=document_id)
        .select_related("mestre__revisao_atual", "workflow_status__etapa")
        .prefetch_related(
            Prefetch("registros_ld", queryset=DocumentoLD.objects.order_by("id"), to_attr="d360_ld"),
            Prefetch("referencias_externas", queryset=DocumentoReferenciaExterna.objects.order_by("id"), to_attr="d360_references"),
            Prefetch("pcfs_timeline", queryset=PCFTimeline.objects.order_by("id"), to_attr="d360_pcfs"),
            Prefetch("transmittals_km", queryset=TransmittalKM.objects.order_by("id"), to_attr="d360_transmittals"),
            Prefetch("arquivos", queryset=ArquivoDocumento.objects.order_by("id"), to_attr="d360_files"),
            Prefetch("versoes", queryset=DocumentoVersao.objects.select_related("criado_por").order_by("id"), to_attr="d360_versions"),
            Prefetch("historico_workflow", queryset=DocumentoWorkflowHistorico.objects.select_related("etapa", "usuario").order_by("data", "id"), to_attr="d360_history"),
            Prefetch("aprovacoes", queryset=DocumentoAprovacao.objects.select_related("etapa", "usuario").order_by("data", "id"), to_attr="d360_approvals"),
            Prefetch("logs", queryset=LogAuditoria.objects.select_related("usuario").order_by("data", "id"), to_attr="d360_logs"),
            Prefetch("pendencias", queryset=PendenciaDocumental.objects.select_related("responsavel").order_by("id"), to_attr="d360_pending"),
            Prefetch("mestre__revisoes", queryset=Documento.objects.order_by("id"), to_attr="d360_revisions"),
        )
        .order_by("id")
        .first()
    )
