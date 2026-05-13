"""
Serviço de auditoria das buscas globais do GED.

Mantém a gravação isolada para que falhas de auditoria nunca quebrem a busca.
"""

from __future__ import annotations

from typing import Any

from apps.automacoes.models import SearchAudit


def registrar_busca(
    *,
    termo: str,
    tipo: str = "todos",
    origem: str = SearchAudit.ORIGEM_WEB,
    usuario: Any = None,
    totais_reais: dict[str, int] | None = None,
    total_geral: int | None = None,
    duracao_ms: int = 0,
    sucesso: bool = True,
    mensagem: str = "",
) -> SearchAudit | None:
    """Registra uma busca global sem propagar erro para a camada de UI."""
    termo = str(termo or "").strip()
    if not termo:
        return None

    totais_reais = totais_reais or {}

    usuario_valido = usuario if getattr(usuario, "is_authenticated", False) else None

    try:
        return SearchAudit.objects.create(
            usuario=usuario_valido,
            termo=termo[:500],
            tipo=str(tipo or "todos")[:50],
            origem=str(origem or SearchAudit.ORIGEM_WEB)[:30],
            total_geral=int(total_geral if total_geral is not None else sum(totais_reais.values())),
            total_km=int(totais_reais.get("km") or 0),
            total_transmittals=int(totais_reais.get("transmittals") or 0),
            total_ld=int(totais_reais.get("ld") or 0),
            total_pcfs=int(totais_reais.get("pcfs") or 0),
            duracao_ms=max(int(duracao_ms or 0), 0),
            sucesso=bool(sucesso),
            mensagem=str(mensagem or ""),
        )
    except Exception:
        return None
