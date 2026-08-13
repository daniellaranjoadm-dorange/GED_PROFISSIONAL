from django.db.models import Count, Prefetch, Q

from apps.automacoes.models import DocumentoLD
from apps.documentos.models import Documento, DocumentoReferenciaExterna


def consulta_central_documentos(*, busca="", vinculo="", dox=""):
    queryset = (
        Documento.objects.filter(ativo=True, deletado_em__isnull=True)
        .select_related("projeto", "etapa")
        .annotate(
            total_registros_ld=Count("registros_ld", distinct=True),
            total_referencias=Count("referencias_externas", distinct=True),
            total_referencias_dox=Count(
                "referencias_externas",
                filter=Q(referencias_externas__sistema=DocumentoReferenciaExterna.SISTEMA_DOX),
                distinct=True,
            ),
        )
    )

    if busca:
        queryset = queryset.filter(
            Q(codigo__icontains=busca)
            | Q(titulo__icontains=busca)
            | Q(disciplina__icontains=busca)
            | Q(registros_ld__documento__icontains=busca)
            | Q(registros_ld__numero_interno__icontains=busca)
            | Q(registros_ld__numero_documento_km__icontains=busca)
            | Q(registros_ld__pcf__icontains=busca)
            | Q(registros_ld__grd__icontains=busca)
            | Q(referencias_externas__identificador_externo__icontains=busca)
        ).distinct()

    if vinculo == "com_ld":
        queryset = queryset.filter(total_registros_ld__gt=0)
    elif vinculo == "sem_ld":
        queryset = queryset.filter(total_registros_ld=0)

    if dox == "com_dox":
        queryset = queryset.filter(total_referencias_dox__gt=0)
    elif dox == "sem_dox":
        queryset = queryset.filter(total_referencias_dox=0)

    return queryset.order_by("codigo", "revisao")


def carregar_relacionamentos_da_pagina(pagina):
    return pagina.object_list.prefetch_related(
        Prefetch(
            "registros_ld",
            queryset=DocumentoLD.objects.order_by("-atualizado_em"),
            to_attr="ld_relacionadas",
        ),
        Prefetch(
            "referencias_externas",
            queryset=DocumentoReferenciaExterna.objects.order_by("sistema", "identificador_externo"),
            to_attr="referencias_carregadas",
        ),
    )


def metricas_central_documentos() -> dict[str, int]:
    documentos = Documento.objects.filter(ativo=True, deletado_em__isnull=True)
    total = documentos.count()
    com_ld = documentos.filter(registros_ld__isnull=False).distinct().count()
    com_dox = documentos.filter(
        referencias_externas__sistema=DocumentoReferenciaExterna.SISTEMA_DOX
    ).distinct().count()
    return {
        "total": total,
        "com_ld": com_ld,
        "sem_ld": max(total - com_ld, 0),
        "com_dox": com_dox,
        "ld_sem_vinculo": DocumentoLD.objects.filter(documento_ged__isnull=True).count(),
    }
