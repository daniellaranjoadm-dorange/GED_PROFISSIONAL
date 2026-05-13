"""
Ranking determinístico para a Busca Global Enterprise do GED.

Mantém regras simples, testáveis e sem dependência de banco para melhorar
a relevância dos resultados antes de qualquer solução externa de full-text.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any


PONTOS_EXTENSAO = {
    ".dwg": 100,
    ".dxf": 96,
    ".docx": 90,
    ".doc": 86,
    ".xlsx": 80,
    ".xlsm": 78,
    ".xls": 74,
    ".pdf": 50,
}

PENALIDADE_TRANSMITTAL_LETTER = 120
BONUS_DOCUMENTO_TECNICO = 35


def normalizar_compacto(valor: Any) -> str:
    """Normaliza texto para comparação forte, preservando apenas alfanuméricos."""
    return "".join(ch for ch in str(valor or "").upper() if ch.isalnum())


def extensao_de(valor: Any) -> str:
    """Extrai extensão em minúsculas de nome/caminho."""
    texto = str(valor or "").strip()
    if not texto:
        return ""
    return Path(texto).suffix.lower()


def eh_transmittal_letter(valor: Any) -> bool:
    """Detecta sinais comuns de Transmittal Letter para reduzir prioridade."""
    texto = str(valor or "").replace("/", "\\").lower()
    nome = Path(texto).name.lower()
    return (
        "transmittal letter" in texto
        or "\\0 transmittal letters\\" in texto
        or nome.startswith("t-")
        or nome.startswith("transmittal")
    )


def score_match_textual(termo: Any, *valores: Any) -> int:
    """
    Pontua aderência textual básica.

    Ordem de força:
    - match exato textual
    - prefixo
    - contains
    - match compacto exato
    - contains compacto
    """
    termo_texto = str(termo or "").strip().lower()
    termo_compacto = normalizar_compacto(termo)

    if not termo_texto and not termo_compacto:
        return 0

    melhor = 0

    for valor in valores:
        texto = str(valor or "").strip()
        if not texto:
            continue

        texto_lower = texto.lower()
        texto_compacto = normalizar_compacto(texto)

        if termo_texto and texto_lower == termo_texto:
            melhor = max(melhor, 120)
        elif termo_texto and texto_lower.startswith(termo_texto):
            melhor = max(melhor, 100)
        elif termo_texto and termo_texto in texto_lower:
            melhor = max(melhor, 80)

        if termo_compacto and texto_compacto == termo_compacto:
            melhor = max(melhor, 115)
        elif termo_compacto and termo_compacto in texto_compacto:
            melhor = max(melhor, 85)

    return melhor


def bonus_extensao(valor: Any) -> int:
    """Retorna bônus por extensão técnica conhecida."""
    return PONTOS_EXTENSAO.get(extensao_de(valor), 10 if str(valor or "").strip() else 0)


def score_documento(
    termo: Any,
    *,
    titulo: Any = "",
    identificador: Any = "",
    descricao: Any = "",
    caminho: Any = "",
    extensao: Any = "",
    eh_transmittal: bool = False,
    documento_tecnico: bool = True,
    base_score: int | None = None,
) -> int:
    """
    Calcula score determinístico para documentos da busca global.

    Não acessa banco e não depende de Django, permitindo testes rápidos.
    """
    score = base_score if base_score is not None else score_match_textual(
        termo,
        titulo,
        identificador,
        descricao,
        caminho,
    )

    alvo_extensao = extensao or caminho or titulo
    score += bonus_extensao(alvo_extensao)

    if documento_tecnico:
        score += BONUS_DOCUMENTO_TECNICO

    if eh_transmittal or eh_transmittal_letter(caminho) or eh_transmittal_letter(titulo):
        score -= PENALIDADE_TRANSMITTAL_LETTER

    return max(int(score), 0)


def ordenar_por_score(resultados: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Ordena resultados por score decrescente e título crescente."""
    return sorted(
        resultados,
        key=lambda item: (int(item.get("score") or 0), str(item.get("titulo") or "").lower()),
        reverse=True,
    )
