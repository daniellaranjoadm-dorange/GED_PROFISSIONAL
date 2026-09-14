def serialize_project(project):
    return {
        "id": project.pk,
        "name": project.nome,
        "client": project.cliente,
        "active": project.ativo,
    }


def serialize_document(document):
    master = document.mestre
    current = master.revisao_atual if master else None
    # Do not expose a hidden revision, or reinterpret an inconsistent pointer.
    if current and (
        not current.ativo
        or current.deletado_em is not None
        or current.mestre_id != master.pk
    ):
        current = None
    return {
        "id": document.pk,
        "master_id": document.mestre_id,
        "document_number": document.codigo,
        "title": document.titulo,
        "revision": document.revisao,
        "current_revision_id": current.pk if current else None,
        "current_revision": current.revisao if current else None,
        "is_current_revision": bool(current and current.pk == document.pk),
        "project": {
            "id": document.projeto_id,
            "name": document.projeto.nome,
        } if document.projeto_id is not None else None,
        "discipline": document.disciplina,
        "document_type": document.tipo_doc,
        "status": document.status_documento,
    }

def serialize_document_ld(record):
    return {
        "id": record.pk,
        "source": record.origem_aba,
        "document_number": record.documento,
        "revision": record.revisao,
        "title": record.titulo,
        "discipline": record.disciplina,
        "document_status": record.status_documento,
        "grd_status": record.status_grd,
        "grd": record.grd,
        "grd_date": record.data_grd,
        "pcf": record.pcf,
        "pcf_date": record.data_pcf,
        "pcf_final_status": record.status_final_pcf,
        "responsible_for_issue": record.resp_for_issue,
        "internal_number": record.numero_interno,
        "hull": record.casco,
        "comment_count": record.qtd_comentarios,
        "open_comments": record.open_comments,
        "issuance_measurement": record.medicao_emissao,
        "approval_measurement": record.medicao_aprovacao,
        "schedule_start": record.cronograma_inicio,
        "schedule_end": record.cronograma_termino,
        "km_document_number": record.numero_documento_km,
        "km_transmittal": record.transmittal_km,
        "km_received_date": record.data_recebimento_km,
        "km_file_found": record.arquivo_km_encontrado,
        "km_link_status": record.status_vinculo_km,
        "km_link_score": record.score_vinculo_km,
        "km_revision": record.revisao_km,
        "km_revision_status": record.status_revisao_km,
        "updated_at": (
            record.atualizado_em.isoformat()
            if record.atualizado_em
            else None
        ),
    }


def serialize_external_reference(reference):
    return {
        "id": reference.pk,
        "system": reference.sistema,
        "external_identifier": reference.identificador_externo,
        "url": reference.url or None,
        "external_status": reference.status_externo or None,
        "divergent": reference.divergente,
        "checked_at": (
            reference.conferido_em.isoformat()
            if reference.conferido_em
            else None
        ),
        "synchronized_at": (
            reference.sincronizado_em.isoformat()
            if reference.sincronizado_em
            else None
        ),
    }


def serialize_document_center(document):
    base = serialize_document(document)

    ld_records = getattr(document, "ld_relacionadas", None)
    if ld_records is None:
        ld_records = document.registros_ld.all()

    external_references = getattr(
        document,
        "referencias_carregadas",
        None,
    )
    if external_references is None:
        external_references = document.referencias_externas.all()

    base["ld_records"] = [
        serialize_document_ld(record)
        for record in ld_records
    ]
    base["external_references"] = [
        serialize_external_reference(reference)
        for reference in external_references
    ]

    return base
