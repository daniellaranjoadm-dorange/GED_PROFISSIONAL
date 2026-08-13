from django.db.models import Q

from apps.automacoes.models import DocumentoLD
from apps.automacoes.services.document_registry_sync import (
    normalizar_identificador,
    normalizar_revisao,
)
from apps.documentos.models import Documento


def consulta_pendencias_ld(*, busca="", origem=""):
    queryset = DocumentoLD.objects.filter(documento_ged__isnull=True).exclude(documento="")
    if busca:
        queryset = queryset.filter(
            Q(documento__icontains=busca)
            | Q(numero_interno__icontains=busca)
            | Q(titulo__icontains=busca)
            | Q(numero_documento_km__icontains=busca)
            | Q(pcf__icontains=busca)
            | Q(grd__icontains=busca)
        )
    if origem:
        queryset = queryset.filter(origem_aba=origem)
    return queryset.order_by("origem_aba", "documento", "revisao")


def origens_pendentes() -> list[str]:
    return list(
        DocumentoLD.objects.filter(documento_ged__isnull=True)
        .exclude(origem_aba="")
        .values_list("origem_aba", flat=True)
        .distinct()
        .order_by("origem_aba")
    )


def adicionar_sugestoes_explicaveis(registros):
    """Sugere candidatos por identificador exato; nunca persiste o vínculo."""
    indice: dict[str, list[Documento]] = {}
    for documento in Documento.objects.filter(ativo=True, deletado_em__isnull=True).only(
        "id", "codigo", "revisao", "titulo"
    ):
        indice.setdefault(normalizar_identificador(documento.codigo), []).append(documento)

    for registro in registros:
        sugestoes = []
        chaves = [
            (normalizar_identificador(registro.documento), "Mesmo código documental"),
            (normalizar_identificador(registro.numero_interno), "Código GED/DOX interno"),
        ]
        vistos = set()
        for chave, motivo in chaves:
            if not chave:
                continue
            for candidato in indice.get(chave, []):
                if candidato.pk in vistos:
                    continue
                vistos.add(candidato.pk)
                revisao_igual = normalizar_revisao(candidato.revisao) == normalizar_revisao(
                    registro.revisao
                )
                sugestoes.append(
                    {
                        "documento": candidato,
                        "motivo": motivo,
                        "revisao_igual": revisao_igual,
                    }
                )
        registro.sugestoes_ged = sugestoes[:5]
    return registros
