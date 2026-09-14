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
