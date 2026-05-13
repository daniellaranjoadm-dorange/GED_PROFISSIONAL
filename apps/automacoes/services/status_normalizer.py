"""
Normalização centralizada de status usados nos dashboards e relatórios.

Mantém a regra em um único ponto para evitar duplicidade como:
Released, released, RELEASED, released with comments etc.
"""

import re


_STATUS_ALIASES = {
    "": "SEM STATUS",
    "-": "SEM STATUS",
    "NA": "SEM STATUS",
    "N/A": "SEM STATUS",
    "NONE": "SEM STATUS",
    "NULL": "SEM STATUS",
    "NAN": "SEM STATUS",
    "SEM STATUS": "SEM STATUS",
    "NOT RELEASED": "NOT RELEASED",
    "RELEASED": "RELEASED",
    "RELEASED WITH COMMENTS": "RELEASED WITH COMMENTS",
}


def normalizar_status(valor, fallback="SEM STATUS"):
    """
    Normaliza status textuais para comparação, agrupamento e dashboards.

    Exemplos:
    - "released" -> "RELEASED"
    - " Released " -> "RELEASED"
    - "released with comments" -> "RELEASED WITH COMMENTS"
    - "" / None -> "SEM STATUS"
    """

    texto = str(valor or "").strip().upper()
    texto = re.sub(r"\s+", " ", texto)

    if not texto:
        return fallback

    return _STATUS_ALIASES.get(texto, texto)
