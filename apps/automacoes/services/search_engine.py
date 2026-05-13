"""
Motor de busca global do GED.

Esta primeira versão é propositalmente simples e segura:
- não altera banco
- não depende de views/templates
- não faz varredura de rede
- usa apenas os modelos já indexados no banco

A evolução futura pode adicionar ranking avançado, autocomplete,
analytics de pesquisa e busca full-text.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from django.db.models import Q

from apps.automacoes.models import DocumentoLD, KMFileIndex


DEFAULT_LIMIT = 20


@dataclass(frozen=True)
class SearchResult:
    origem: str
    titulo: str
    subtitulo: str = ""
    identificador: str = ""
    url: str = ""
    score: int = 0
    payload: dict[str, Any] | None = None

    def as_dict(self) -> dict[str, Any]:
        return {
            "origem": self.origem,
            "titulo": self.titulo,
            "subtitulo": self.subtitulo,
            "identificador": self.identificador,
            "url": self.url,
            "score": self.score,
            "payload": self.payload or {},
        }


def normalizar_termo_busca(termo: str | None) -> str:
    """Normaliza o termo digitado sem remover caracteres úteis como hífen."""
    return str(termo or "").strip()


def _valor_modelo(objeto: Any, *campos: str, default: str = "") -> str:
    for campo in campos:
        if hasattr(objeto, campo):
            valor = getattr(objeto, campo, None)
            if valor not in (None, ""):
                return str(valor)
    return default


def _buscar_ld(termo: str, limit: int) -> list[dict[str, Any]]:
    if not termo:
        return []

    qs = DocumentoLD.objects.all()

    filtros = Q()
    campos_busca = [
        "documento",
        "titulo",
        "descricao",
        "disciplina",
        "pcf",
        "grd",
        "resposta",
    ]

    for campo in campos_busca:
        try:
            DocumentoLD._meta.get_field(campo)
        except Exception:
            continue
        filtros |= Q(**{f"{campo}__icontains": termo})

    if not filtros:
        return []

    resultados = []
    for item in qs.filter(filtros).order_by("id")[:limit]:
        documento = _valor_modelo(item, "documento", "codigo", "numero", default=f"LD #{item.pk}")
        titulo = _valor_modelo(item, "titulo", "descricao", default=documento)
        subtitulo = _valor_modelo(item, "disciplina", "status", default="")
        resultados.append(
            SearchResult(
                origem="LD",
                titulo=titulo,
                subtitulo=subtitulo,
                identificador=documento,
                score=80,
                payload={"pk": item.pk},
            ).as_dict()
        )

    return resultados


def _buscar_km(termo: str, limit: int) -> list[dict[str, Any]]:
    if not termo:
        return []

    qs = KMFileIndex.objects.filter(ativo=True).filter(
        Q(nome_arquivo__icontains=termo)
        | Q(caminho_completo__icontains=termo)
        | Q(documento_extraido__icontains=termo)
        | Q(nome_normalizado__icontains="".join(ch for ch in termo.upper() if ch.isalnum()))
        | Q(stem_normalizado__icontains="".join(ch for ch in termo.upper() if ch.isalnum()))
    )

    resultados = []
    for item in qs.order_by("-indexado_em", "nome_arquivo")[:limit]:
        resultados.append(
            SearchResult(
                origem="KM",
                titulo=item.nome_arquivo or item.caminho_completo,
                subtitulo=item.pasta or "",
                identificador=item.documento_extraido or item.nome_arquivo or "",
                score=70 if not item.eh_transmittal_letter else 40,
                payload={
                    "pk": item.pk,
                    "caminho_completo": item.caminho_completo,
                    "eh_transmittal_letter": item.eh_transmittal_letter,
                },
            ).as_dict()
        )

    return resultados


def buscar_global(termo: str | None, limit: int = DEFAULT_LIMIT) -> dict[str, Any]:
    """
    Executa busca global inicial em LD e índice KM.

    Retorna estrutura estável para views, APIs e testes futuros.
    """
    termo_normalizado = normalizar_termo_busca(termo)
    limit = max(int(limit or DEFAULT_LIMIT), 1)

    if not termo_normalizado:
        return {
            "termo": "",
            "total": 0,
            "ld": [],
            "km": [],
            "resultados": [],
        }

    ld = _buscar_ld(termo_normalizado, limit)
    km = _buscar_km(termo_normalizado, limit)

    resultados = sorted(
        [*ld, *km],
        key=lambda item: (item.get("score", 0), item.get("origem", "")),
        reverse=True,
    )

    return {
        "termo": termo_normalizado,
        "total": len(resultados),
        "ld": ld,
        "km": km,
        "resultados": resultados,
    }
