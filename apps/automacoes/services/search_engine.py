"""
Motor de busca global do GED.

Esta versão mantém compatibilidade com os testes iniciais via ``buscar_global``
e também fornece uma camada pronta para a tela enterprise de busca global.
"""

from __future__ import annotations

from dataclasses import dataclass
import time
from typing import Any
from urllib.parse import quote

from django.db.models import Q

from apps.automacoes.models import DocumentoLD, KMFileIndex, PCFTimeline, SearchAudit, TransmittalKM
from apps.automacoes.services.search_audit import registrar_busca
from apps.automacoes.services.search_ranker import ordenar_por_score, score_documento


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


def _termo_compacto(termo: str | None) -> str:
    return "".join(ch for ch in str(termo or "").upper() if ch.isalnum())


def _valor_modelo(objeto: Any, *campos: str, default: str = "") -> str:
    for campo in campos:
        if hasattr(objeto, campo):
            valor = getattr(objeto, campo, None)
            if valor not in (None, ""):
                return str(valor)
    return default


def _model_has_field(model: Any, campo: str) -> bool:
    try:
        model._meta.get_field(campo)
        return True
    except Exception:
        return False


def _montar_filtro_modelo(model: Any, termo: str, campos: list[str]) -> Q:
    filtro = Q()
    for campo in campos:
        if _model_has_field(model, campo):
            filtro |= Q(**{f"{campo}__icontains": termo})
    return filtro


def _bg_score(termo: str, *valores: Any) -> int:
    termo_limpo = normalizar_termo_busca(termo).lower()
    termo_compacto = _termo_compacto(termo)

    if not termo_limpo:
        return 0

    melhor = 10

    for valor in valores:
        texto = str(valor or "").strip()
        if not texto:
            continue

        texto_lower = texto.lower()
        texto_compacto = _termo_compacto(texto)

        if texto_lower == termo_limpo:
            melhor = max(melhor, 100)
        elif texto_lower.startswith(termo_limpo):
            melhor = max(melhor, 88)
        elif termo_limpo in texto_lower:
            melhor = max(melhor, 72)

        if termo_compacto and texto_compacto == termo_compacto:
            melhor = max(melhor, 96)
        elif termo_compacto and termo_compacto in texto_compacto:
            melhor = max(melhor, 76)

    return melhor


def _limitar(qs: Any, limit: int) -> list[Any]:
    return list(qs[: max(int(limit or DEFAULT_LIMIT), 1)])


def _buscar_ld(termo: str, limit: int) -> list[dict[str, Any]]:
    if not termo:
        return []

    campos_busca = [
        "documento",
        "titulo",
        "descricao",
        "disciplina",
        "status",
        "status_documento",
        "status_grd",
        "pcf",
        "grd",
        "resposta",
        "pcf_resposta",
        "grd_resposta",
    ]
    filtros = _montar_filtro_modelo(DocumentoLD, termo, campos_busca)

    if not filtros:
        return []

    resultados = []
    for item in DocumentoLD.objects.filter(filtros).order_by("documento", "revisao", "id")[:limit]:
        documento = _valor_modelo(item, "documento", "codigo", "numero", default=f"LD #{item.pk}")
        titulo = _valor_modelo(item, "titulo", "descricao", default=documento)
        subtitulo = _valor_modelo(item, "disciplina", "status", default="")
        resultados.append(
            SearchResult(
                origem="LD",
                titulo=titulo,
                subtitulo=subtitulo,
                identificador=documento,
                score=_bg_score(termo, documento, titulo, subtitulo),
                payload={"pk": item.pk},
            ).as_dict()
        )

    return resultados


def _buscar_km(termo: str, limit: int) -> list[dict[str, Any]]:
    if not termo:
        return []

    termo_norm = _termo_compacto(termo)
    qs = KMFileIndex.objects.filter(ativo=True).filter(
        Q(nome_arquivo__icontains=termo)
        | Q(caminho_completo__icontains=termo)
        | Q(pasta__icontains=termo)
        | Q(documento_extraido__icontains=termo)
        | Q(nome_normalizado__icontains=termo_norm)
        | Q(stem_normalizado__icontains=termo_norm)
    )

    resultados = []
    for item in qs.order_by("eh_transmittal_letter", "-indexado_em", "nome_arquivo")[:limit]:
        score = _bg_score(termo, item.nome_arquivo, item.documento_extraido, item.caminho_completo)
        if item.eh_transmittal_letter:
            score = max(score - 20, 10)

        resultados.append(
            SearchResult(
                origem="KM",
                titulo=item.nome_arquivo or item.caminho_completo,
                subtitulo=item.documento_extraido or item.extensao or "",
                identificador=item.documento_extraido or item.nome_arquivo or "",
                score=score,
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

    Mantém o contrato original dos testes e integrações já criadas.
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


def _item_km_enterprise(item: KMFileIndex, termo: str) -> dict[str, Any]:
    titulo = item.nome_arquivo or item.caminho_completo
    identificador = item.documento_extraido or item.nome_arquivo or ""
    descricao = item.pasta or item.caminho_completo
    return {
        "id": item.id,
        "tipo": "KM",
        "titulo": titulo,
        "subtitulo": item.documento_extraido or item.extensao or "Arquivo KM",
        "descricao": descricao,
        "badge": "Transmittal Letter" if item.eh_transmittal_letter else "Documento KM",
        "score": score_documento(
            termo,
            titulo=titulo,
            identificador=identificador,
            descricao=descricao,
            caminho=item.caminho_completo,
            extensao=item.extensao,
            eh_transmittal=item.eh_transmittal_letter,
            documento_tecnico=not item.eh_transmittal_letter,
            base_score=_bg_score(termo, item.nome_arquivo, item.documento_extraido, item.caminho_completo),
        ),
        "abrir_url": f"/automacoes/km-index/{item.id}/abrir/",
        "pasta_url": f"/automacoes/km-index/{item.id}/abrir-pasta/",
    }


def _item_transmittal_enterprise(item: TransmittalKM, termo: str) -> dict[str, Any]:
    q_url = quote(termo)
    return {
        "id": item.id,
        "tipo": "Transmittal KM",
        "titulo": item.documento or item.transmittal_numero or "Registro KM",
        "subtitulo": item.transmittal_numero or "Sem transmittal",
        "descricao": item.titulo or item.pasta or "",
        "badge": item.status_parse or "KM",
        "score": score_documento(
            termo,
            titulo=item.documento or item.transmittal_numero or "Registro KM",
            identificador=item.transmittal_numero,
            descricao=item.titulo or item.pasta,
            caminho=item.arquivo_pdf,
            eh_transmittal=True,
            documento_tecnico=False,
            base_score=_bg_score(termo, item.documento, item.titulo, item.transmittal_numero, item.pasta),
        ),
        "abrir_url": f"/automacoes/transmittals-km/{item.id}/abrir-documento/",
        "pasta_url": f"/automacoes/transmittals-km/{item.id}/abrir-pasta/",
        "registro_url": f"/automacoes/transmittals-km/?q={q_url}",
    }


def _item_ld_enterprise(item: DocumentoLD, termo: str) -> dict[str, Any]:
    q_url = quote(termo)
    revisao = _valor_modelo(item, "revisao", default="—")
    disciplina = _valor_modelo(item, "disciplina", default="Sem disciplina")
    return {
        "id": item.id,
        "tipo": "LD",
        "titulo": _valor_modelo(item, "documento", default="Documento LD"),
        "subtitulo": f"Rev. {revisao or '—'} · {disciplina or 'Sem disciplina'}",
        "descricao": _valor_modelo(item, "titulo", "descricao", default=""),
        "badge": _valor_modelo(item, "status_documento", "status_grd", "status", default="LD"),
        "score": score_documento(
            termo,
            titulo=_valor_modelo(item, "documento"),
            identificador=_valor_modelo(item, "documento"),
            descricao=_valor_modelo(item, "titulo"),
            caminho=_valor_modelo(item, "caminho_documento", "caminho_grd", "caminho_pcf"),
            documento_tecnico=True,
            base_score=_bg_score(
                termo,
                _valor_modelo(item, "documento"),
                _valor_modelo(item, "titulo"),
                _valor_modelo(item, "disciplina"),
                _valor_modelo(item, "grd"),
                _valor_modelo(item, "pcf"),
            ),
        ),
        "abrir_url": f"/automacoes/ld/{item.id}/abrir/documento/",
        "registro_url": f"/automacoes/ld/?q={q_url}",
    }


def _item_pcf_enterprise(item: PCFTimeline, termo: str) -> dict[str, Any]:
    q_url = quote(termo)
    return {
        "id": item.id,
        "tipo": "PCF",
        "titulo": item.numero_documento or item.numero_pcf or "PCF",
        "subtitulo": f"{item.tipo or 'PCF'} · Rev. {item.revisao_pcf or '—'}",
        "descricao": item.titulo or "",
        "badge": item.status_final or "PCF",
        "score": score_documento(
            termo,
            titulo=item.numero_documento or item.numero_pcf or "PCF",
            identificador=item.numero_pcf,
            descricao=item.titulo,
            caminho=item.caminho,
            documento_tecnico=True,
            base_score=_bg_score(termo, item.numero_documento, item.numero_pcf, item.titulo, item.status_final),
        ),
        "abrir_url": f"/automacoes/pcfs/{item.id}/abrir-arquivo/",
        "registro_url": f"/automacoes/pcfs/?q={q_url}",
    }


def buscar_global_enterprise(
    q: str | None,
    tipo: str = "todos",
    *,
    limit_km: int = 30,
    limit_transmittals: int = 25,
    limit_ld: int = 25,
    limit_pcfs: int = 25,
    usuario: Any = None,
    origem: str = SearchAudit.ORIGEM_WEB,
    auditar: bool = False,
) -> dict[str, Any]:
    """
    Retorna contexto completo para o template enterprise de busca global.

    A função não renderiza template e não altera banco. Assim pode ser usada por
    views, APIs e testes sem acoplar regra de busca ao ``views.py``.
    """
    inicio = time.monotonic()
    termo = normalizar_termo_busca(q)
    tipo_normalizado = (tipo or "todos").strip().lower() or "todos"

    if tipo_normalizado not in {"todos", "km", "transmittal", "transmittals", "ld", "pcf", "pcfs"}:
        tipo_normalizado = "todos"

    resultados = {
        "km": [],
        "transmittals": [],
        "ld": [],
        "pcfs": [],
    }

    totais_reais = {
        "km": 0,
        "transmittals": 0,
        "ld": 0,
        "pcfs": 0,
    }

    totais = {
        "geral": 0,
    }

    if len(termo) < 2:
        contexto = {
            "q": termo,
            "tipo": tipo_normalizado,
            "resultados": resultados,
            "totais": totais,
            "totais_reais": totais_reais,
        }
        if auditar and termo:
            registrar_busca(
                termo=termo,
                tipo=tipo_normalizado,
                origem=origem,
                usuario=usuario,
                totais_reais=totais_reais,
                total_geral=0,
                duracao_ms=round((time.monotonic() - inicio) * 1000),
                sucesso=True,
                mensagem="Termo com menos de 2 caracteres.",
            )
        return contexto

    termo_norm = _termo_compacto(termo)

    if tipo_normalizado in {"todos", "km"}:
        km_qs = KMFileIndex.objects.filter(ativo=True).filter(
            Q(nome_arquivo__icontains=termo)
            | Q(caminho_completo__icontains=termo)
            | Q(pasta__icontains=termo)
            | Q(documento_extraido__icontains=termo)
            | Q(nome_normalizado__icontains=termo_norm)
            | Q(stem_normalizado__icontains=termo_norm)
        ).order_by("eh_transmittal_letter", "nome_arquivo")

        totais_reais["km"] = km_qs.count()
        resultados["km"] = ordenar_por_score([
            _item_km_enterprise(item, termo)
            for item in _limitar(km_qs, limit_km)
        ])

    if tipo_normalizado in {"todos", "transmittal", "transmittals"}:
        tr_qs = TransmittalKM.objects.filter(
            Q(documento__icontains=termo)
            | Q(titulo__icontains=termo)
            | Q(pasta__icontains=termo)
            | Q(emissao__icontains=termo)
            | Q(proposito_emissao__icontains=termo)
            | Q(transmittal_numero__icontains=termo)
        ).order_by("transmittal_numero", "documento")

        totais_reais["transmittals"] = tr_qs.count()
        resultados["transmittals"] = ordenar_por_score([
            _item_transmittal_enterprise(item, termo)
            for item in _limitar(tr_qs, limit_transmittals)
        ])

    if tipo_normalizado in {"todos", "ld"}:
        ld_qs = DocumentoLD.objects.filter(
            Q(documento__icontains=termo)
            | Q(titulo__icontains=termo)
            | Q(disciplina__icontains=termo)
            | Q(status_documento__icontains=termo)
            | Q(status_grd__icontains=termo)
            | Q(grd__icontains=termo)
            | Q(pcf__icontains=termo)
            | Q(pcf_resposta__icontains=termo)
            | Q(grd_resposta__icontains=termo)
        ).order_by("documento", "revisao", "id")

        totais_reais["ld"] = ld_qs.count()
        resultados["ld"] = ordenar_por_score([
            _item_ld_enterprise(item, termo)
            for item in _limitar(ld_qs, limit_ld)
        ])

    if tipo_normalizado in {"todos", "pcf", "pcfs"}:
        pcfs_qs = PCFTimeline.objects.filter(
            Q(numero_documento__icontains=termo)
            | Q(numero_pcf__icontains=termo)
            | Q(pcf_link__icontains=termo)
            | Q(titulo__icontains=termo)
            | Q(status_final__icontains=termo)
            | Q(tipo__icontains=termo)
        ).order_by("numero_documento", "revisao_pcf", "id")

        totais_reais["pcfs"] = pcfs_qs.count()
        resultados["pcfs"] = ordenar_por_score([
            _item_pcf_enterprise(item, termo)
            for item in _limitar(pcfs_qs, limit_pcfs)
        ])

    totais["geral"] = sum(totais_reais.values())

    contexto = {
        "q": termo,
        "tipo": tipo_normalizado,
        "resultados": resultados,
        "totais": totais,
        "totais_reais": totais_reais,
    }

    if auditar:
        registrar_busca(
            termo=termo,
            tipo=tipo_normalizado,
            origem=origem,
            usuario=usuario,
            totais_reais=totais_reais,
            total_geral=totais["geral"],
            duracao_ms=round((time.monotonic() - inicio) * 1000),
            sucesso=True,
        )

    return contexto
