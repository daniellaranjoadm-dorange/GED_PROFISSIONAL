"""
Jobs gerenciados para indexação KM.

Este módulo desacopla a rotina pesada de indexação KM da camada de views.
A execução ainda é síncrona nesta fase, mas passa a ser rastreada por
JobExecution via job_manager.
"""

from __future__ import annotations

from typing import Any, Callable

from apps.automacoes.services.job_manager import executar_job_sincrono


def _executar_indexador_km() -> dict[str, Any]:
    """
    Import tardio para evitar dependência circular com views.py.

    A função _km_indexar_banco ainda vive em views.py nesta fase.
    Em sprint futura, ela deverá ser movida para um service próprio.
    """
    from apps.automacoes.views import _km_indexar_banco

    resultado = _km_indexar_banco()
    if isinstance(resultado, dict):
        return resultado

    return {
        "ok": bool(resultado),
        "mensagem": "Indexação KM executada.",
        "resultado": resultado,
    }


def executar_reindexacao_km_job(
    *,
    user=None,
    payload: dict[str, Any] | None = None,
    executor: Callable[[], dict[str, Any]] | None = None,
):
    """
    Executa a reindexação KM como job rastreável.

    Args:
        user: usuário que disparou a execução, quando disponível.
        payload: metadados opcionais da execução.
        executor: função alternativa usada principalmente em testes.

    Returns:
        JobExecution atualizado com status, duração, resultado ou erro.
    """
    executor_final = executor or _executar_indexador_km

    payload_final = {
        "origem": "km_index",
        "modo": "sync",
        **(payload or {}),
    }

    return executar_job_sincrono(
        job_name="km_index_rebuild",
        func=executor_final,
        payload=payload_final,
        user=user,
    )
