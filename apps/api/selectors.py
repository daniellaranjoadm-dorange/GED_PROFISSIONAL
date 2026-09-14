from apps.documentos.models import Documento, Projeto


def projects():
    # Inactive projects remain identifiable; their persisted flag is explicit.
    return Projeto.objects.all().order_by("id")


def documents():
    return (
        Documento.objects.filter(ativo=True, deletado_em__isnull=True)
        .select_related("projeto", "mestre__revisao_atual")
        .order_by("id")
    )
