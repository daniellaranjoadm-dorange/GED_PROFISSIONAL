from django.core.paginator import Paginator
from django.http import JsonResponse

from apps.automacoes.services.document_center import (
    carregar_relacionamentos_da_pagina,
    consulta_central_documentos,
    metricas_central_documentos,
    opcoes_filtros_central_documentos,
)

from .permissions import document_center_read_only
from .responses import positive_integer, validate_parameters
from .serializers import serialize_document_center


DOCUMENT_CENTER_FILTERS = {
    "q",
    "vinculo",
    "dox",
    "tipo",
    "disciplina",
    "status",
    "emissao",
    "status_pcf",
    "responsavel",
    "casco",
    "origem",
    "medicao_emissao",
    "medicao_aprovacao",
    "indicador",
}

DOCUMENT_CENTER_PAGINATION = {"page", "page_size"}


def _filters(params):
    return {
        "busca": params.get("q", "").strip(),
        "vinculo": params.get("vinculo", "").strip(),
        "dox": params.get("dox", "").strip(),
        "tipo": params.get("tipo", "").strip(),
        "disciplina": params.get("disciplina", "").strip(),
        "status": params.get("status", "").strip(),
        "emissao": params.get("emissao", "").strip(),
        "status_pcf": params.get("status_pcf", "").strip(),
        "responsavel": params.get("responsavel", "").strip(),
        "casco": params.get("casco", "").strip(),
        "origem": params.get("origem", "").strip(),
        "medicao_emissao": params.get("medicao_emissao", "").strip(),
        "medicao_aprovacao": params.get("medicao_aprovacao", "").strip(),
        "indicador": params.get("indicador", "").strip(),
    }


def _ld_filters(params):
    return {
        key: params.get(key, "").strip()
        for key in (
            "tipo",
            "disciplina",
            "status",
            "emissao",
            "status_pcf",
            "responsavel",
            "casco",
            "origem",
            "medicao_emissao",
            "medicao_aprovacao",
        )
    }


@document_center_read_only
def document_center_list(request):
    validate_parameters(
        request.GET,
        DOCUMENT_CENTER_FILTERS | DOCUMENT_CENTER_PAGINATION,
    )

    queryset = consulta_central_documentos(**_filters(request.GET))

    page_number = positive_integer(request.GET, "page") or 1
    page_size = positive_integer(request.GET, "page_size") or 50
    page_size = min(page_size, 200)

    paginator = Paginator(queryset, page_size)
    page = paginator.get_page(page_number)

    page.object_list = carregar_relacionamentos_da_pagina(page)

    return JsonResponse(
        {
            "count": paginator.count,
            "page": page.number,
            "page_size": page_size,
            "total_pages": paginator.num_pages,
            "results": [
                serialize_document_center(document)
                for document in page.object_list
            ],
        }
    )


@document_center_read_only
def document_center_metrics(request):
    validate_parameters(request.GET, DOCUMENT_CENTER_FILTERS)

    queryset = consulta_central_documentos(**_filters(request.GET))

    metrics = metricas_central_documentos(
        queryset,
        _ld_filters(request.GET),
    )

    return JsonResponse(metrics)


@document_center_read_only
def document_center_filters(request):
    validate_parameters(request.GET, set())
    return JsonResponse(opcoes_filtros_central_documentos())
