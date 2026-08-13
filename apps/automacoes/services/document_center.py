from django.db.models import Count, Prefetch, Q

from apps.automacoes.models import DocumentoLD
from apps.documentos.models import Documento, DocumentoReferenciaExterna
from apps.automacoes.services.ld_parser import extrair_tipo_documental


def consulta_central_documentos(
    *, busca="", vinculo="", dox="", tipo="", disciplina="", status="",
    emissao="", status_pcf="", responsavel="", casco="", origem=""
):
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

    if tipo:
        ids_tipo = [
            documento.id
            for documento in queryset.only("id", "codigo")
            if extrair_tipo_documental(documento.codigo) == tipo.upper()
        ]
        queryset = queryset.filter(id__in=ids_tipo)
    if disciplina:
        queryset = queryset.filter(
            Q(disciplina__iexact=disciplina)
            | Q(registros_ld__disciplina__iexact=disciplina)
        )
    if status:
        queryset = queryset.filter(registros_ld__status_documento__iexact=status)
    if emissao:
        queryset = queryset.filter(registros_ld__status_grd__iexact=emissao)
    if status_pcf:
        queryset = queryset.filter(registros_ld__status_final_pcf__iexact=status_pcf)
    if responsavel:
        queryset = queryset.filter(registros_ld__resp_for_issue__iexact=responsavel)
    if casco:
        queryset = queryset.filter(registros_ld__casco__iexact=casco)
    if origem:
        queryset = queryset.filter(registros_ld__origem_aba__iexact=origem)

    return queryset.distinct().order_by("codigo", "revisao")


def opcoes_filtros_central_documentos() -> dict[str, list[str]]:
    def distintos(campo):
        return list(
            DocumentoLD.objects.exclude(**{f"{campo}__isnull": True})
            .exclude(**{campo: ""})
            .order_by(campo)
            .values_list(campo, flat=True)
            .distinct()
        )

    tipos = sorted(
        {
            tipo
            for codigo in Documento.objects.filter(
                ativo=True, deletado_em__isnull=True
            ).values_list("codigo", flat=True)
            if (tipo := extrair_tipo_documental(codigo))
        }
    )
    disciplinas = sorted(
        set(distintos("disciplina"))
        | set(
            Documento.objects.filter(ativo=True, deletado_em__isnull=True)
            .exclude(disciplina__isnull=True)
            .exclude(disciplina="")
            .values_list("disciplina", flat=True)
        )
    )
    return {
        "tipos": tipos,
        "disciplinas": disciplinas,
        "status": distintos("status_documento"),
        "emissoes": distintos("status_grd"),
        "status_pcf": distintos("status_final_pcf"),
        "responsaveis": distintos("resp_for_issue"),
        "cascos": distintos("casco"),
        "origens": distintos("origem_aba"),
    }


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


def metricas_central_documentos(documentos=None) -> dict[str, int | float]:
    documentos = documentos or Documento.objects.filter(
        ativo=True, deletado_em__isnull=True
    )
    ids = list(documentos.values_list("id", flat=True).distinct())
    total = len(ids)
    registros = DocumentoLD.objects.filter(documento_ged_id__in=ids)
    com_ld = registros.values("documento_ged_id").distinct().count()
    emitidos_ids = registros.filter(status_grd__iexact="Emitido").values("documento_ged_id")
    emitidos = emitidos_ids.distinct().count()
    recebidos_pendentes = (
        registros.filter(status_documento__icontains="Recebido")
        .exclude(documento_ged_id__in=emitidos_ids)
        .values("documento_ged_id").distinct().count()
    )
    pcf_nao_liberadas = (
        registros.exclude(pcf="")
        .exclude(
            Q(status_final_pcf__iexact="RELEASED")
            | Q(status_final_pcf__iexact="RELEASED WITH COMMENTS")
        )
        .values("documento_ged_id").distinct().count()
    )
    aprovados_sem_comentarios = (
        registros.filter(status_documento__icontains="Aprovado")
        .exclude(status_documento__icontains="coment")
        .values("documento_ged_id").distinct().count()
    )
    comentarios_open = 0
    for valor in registros.exclude(open_comments="").values_list("open_comments", flat=True):
        try:
            comentarios_open += int(float(str(valor).replace(",", ".")))
        except (TypeError, ValueError):
            continue
    com_pcf = registros.exclude(pcf="").values("documento_ged_id").distinct().count()
    return {
        "total": total,
        "com_ld": com_ld,
        "sem_ld": max(total - com_ld, 0),
        "emitidos": emitidos,
        "progresso_emissao": round((emitidos / total) * 100, 1) if total else 0,
        "recebidos_pendentes": recebidos_pendentes,
        "comentarios_open": comentarios_open,
        "pcf_nao_liberadas": pcf_nao_liberadas,
        "aprovados_sem_comentarios": aprovados_sem_comentarios,
        "com_pcf": com_pcf,
        "ld_sem_vinculo": DocumentoLD.objects.filter(documento_ged__isnull=True).count(),
    }
