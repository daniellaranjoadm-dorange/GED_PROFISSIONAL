"""Explicit metadata allowlists. No storage access, URL generation or enrichment."""
from .serializers import serialize_document, serialize_document_ld


def _iso(value):
    return value.isoformat() if value is not None else None


def _user(user):
    return {"id": user.pk, "username": user.username} if user else None


def _stage(stage):
    return {"id": stage.pk, "code": stage.codigo, "name": stage.nome} if stage else None


def _filename(value):
    # Both separators must be handled even when running on Linux.
    # Keep null/empty names; never fall back to a storage path or generate a URL.
    return value.replace("\\", "/").rsplit("/", 1)[-1] if value else value


def serialize_document_360(document):
    master = document.mestre
    state = getattr(document, "workflow_status", None)
    return {
        "document": serialize_document(document),
        "ld_records": [serialize_document_ld(row) for row in document.d360_ld],
        "revisions": [
            {
                "id": row.pk,
                "document_number": row.codigo,
                "revision": row.revisao,
                "status": row.status_documento,
                "project_id": row.projeto_id,
                "active": row.ativo,
                "deleted_at": _iso(row.deletado_em),
                "created_at": _iso(row.criado_em),
                "issued_at": _iso(row.data_emissao_grdt),
                "is_current_revision": row.pk == master.revisao_atual_id,
            }
            for row in (master.d360_revisions if master else [])
        ],
        "pcf_timeline": [
            {
                "id": row.pk, "type": row.tipo,
                "pcf_number": row.numero_pcf, "document_number": row.numero_documento,
                "title": row.titulo, "revision": row.revisao_pcf,
                "received_date": row.data_recebimento,
                "open_comments": row.open_comments, "comment_count": row.qtd_comentarios,
                "final_status": row.status_final,
                "created_at": _iso(row.criado_em), "updated_at": _iso(row.atualizado_em),
            } for row in document.d360_pcfs
        ],
        "transmittals": [
            {
                "id": row.pk, "document_number": row.documento, "title": row.titulo,
                "issuance": row.emissao, "purpose": row.proposito_emissao,
                "sent_date": row.data_envio, "number": row.transmittal_numero,
                "created_at": _iso(row.criado_em), "updated_at": _iso(row.atualizado_em),
            } for row in document.d360_transmittals
        ],
        "external_references": [
            {
                "id": row.pk, "system": row.sistema,
                "external_identifier": row.identificador_externo,
                "external_status": row.status_externo, "divergent": row.divergente,
                "checked_at": _iso(row.conferido_em),
                "synchronized_at": _iso(row.sincronizado_em),
            } for row in document.d360_references
        ],
        "workflow": {
            "document_stage": _stage(document.etapa),
            "legacy_stage": document.etapa_atual,
            "current": {
                "id": state.pk, "stage": _stage(state.etapa),
                "started_at": _iso(state.iniciado_em), "deadline": _iso(state.prazo_final),
            } if state else None,
            "history": [
                {"id": row.pk, "stage": _stage(row.etapa), "user": _user(row.usuario),
                 "action": row.acao, "date": _iso(row.data)}
                for row in document.d360_history
            ],
        },
        "approvals": [
            {"id": row.pk, "stage": _stage(row.etapa), "user": _user(row.usuario),
             "status": row.status, "date": _iso(row.data)}
            for row in document.d360_approvals
        ],
        "files": [
            {"id": row.pk, "name": _filename(row.nome_original), "type": row.tipo,
             "uploaded_at": _iso(row.enviado_em)}
            for row in document.d360_files
        ],
        "versions": [
            {"id": row.pk, "name": _filename(row.arquivo.name),
             "revision": row.numero_revisao, "status": row.status_revisao,
             "created_at": _iso(row.criado_em), "created_by": _user(row.criado_por)}
            for row in document.d360_versions
        ],
        "pending_actions": [
            {"id": row.pk, "ld_record_id": row.registro_ld_id, "type": row.tipo,
             "title": row.titulo, "source": row.origem, "severity": row.severidade,
             "status": row.status, "responsible": _user(row.responsavel),
             "responsible_text": row.responsavel_texto, "deadline": _iso(row.prazo),
             "detected_at": _iso(row.detectada_em), "updated_at": _iso(row.atualizada_em),
             "resolved_at": _iso(row.resolvida_em)}
            for row in document.d360_pending
        ],
        "audit_trail": [
            {"id": row.pk, "user": _user(row.usuario), "action": row.acao,
             "date": _iso(row.data)}
            for row in document.d360_logs
        ],
    }
