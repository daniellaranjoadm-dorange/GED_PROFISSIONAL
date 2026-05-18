"""
Sync Engine KM ↔ LD.

Camada operacional sem migrations:
- executa o motor de vínculo KM ↔ LD existente;
- calcula indicadores de cobertura documental;
- consolida divergências e gaps;
- retorna payload rastreável para JobExecution/ExecucaoAutomacao.
"""

from __future__ import annotations

import time
from typing import Any

from django.db.models import Avg, Count, Q

from apps.automacoes.models import DocumentoKM, DocumentoLD, TransmittalKM
from apps.automacoes.services.document_link_engine import DocumentLinkEngine


def _texto(valor: Any) -> str:
    return str(valor or "").strip()


def _model_has_field(model, nome: str) -> bool:
    return any(field.name == nome for field in model._meta.get_fields())


def _percentual(parte: int, total: int) -> float:
    if not total:
        return 0.0
    return round((parte / total) * 100, 1)


def _contar_documentos_ld_com_km() -> int:
    if not _model_has_field(DocumentoLD, "numero_documento_km"):
        return 0

    return (
        DocumentoLD.objects.exclude(numero_documento_km="")
        .exclude(numero_documento_km__isnull=True)
        .count()
    )


def _contar_revisoes_divergentes() -> int:
    if not _model_has_field(DocumentoLD, "status_revisao_km"):
        return 0

    return DocumentoLD.objects.filter(status_revisao_km__iexact="DIVERGENTE").count()


def _contar_score_baixo() -> int:
    if not _model_has_field(DocumentoLD, "score_vinculo_km"):
        return 0

    return DocumentoLD.objects.filter(score_vinculo_km__gt=0, score_vinculo_km__lt=70).count()


def _score_medio_ld() -> float:
    if not _model_has_field(DocumentoLD, "score_vinculo_km"):
        return 0.0

    valor = DocumentoLD.objects.aggregate(media=Avg("score_vinculo_km")).get("media") or 0
    return round(float(valor), 1)


def _sincronizar_recebimento_documentokm() -> dict[str, int]:
    """
    Marca DocumentoKM como recebido quando houver TransmittalKM correspondente.

    Mantém regra defensiva:
    - não cria documentos;
    - não sobrescreve vínculo manual;
    - usa correspondência simples por número KM/documento.
    """

    if not DocumentoKM.objects.exists():
        return {"documentos_km": 0, "recebidos_atualizados": 0}

    transmittals = {
        _texto(item["documento"]).upper(): item
        for item in TransmittalKM.objects.exclude(documento="")
        .values("documento", "transmittal_numero", "data_envio")
    }

    atualizados = 0

    for doc in DocumentoKM.objects.all().iterator(chunk_size=500):
        chave = _texto(doc.numero_km).upper()
        evento = transmittals.get(chave)

        if not evento:
            continue

        campos_update = []

        if doc.status_recebimento != DocumentoKM.STATUS_RECEBIMENTO_RECEBIDO:
            doc.status_recebimento = DocumentoKM.STATUS_RECEBIMENTO_RECEBIDO
            campos_update.append("status_recebimento")

        transmittal_numero = _texto(evento.get("transmittal_numero"))
        if transmittal_numero and doc.transmittal_numero != transmittal_numero:
            doc.transmittal_numero = transmittal_numero
            campos_update.append("transmittal_numero")

        data_envio = _texto(evento.get("data_envio"))
        if data_envio and doc.data_recebimento_km != data_envio:
            doc.data_recebimento_km = data_envio
            campos_update.append("data_recebimento_km")

        if campos_update:
            campos_update.append("atualizado_em")
            doc.save(update_fields=campos_update)
            atualizados += 1

    return {
        "documentos_km": DocumentoKM.objects.count(),
        "recebidos_atualizados": atualizados,
    }


def executar_sync_km_ld(*, limite_candidatos: int = 300) -> dict[str, Any]:
    """
    Executa sincronização operacional KM ↔ LD.

    Returns:
        dict serializável para logs, JobExecution e dashboards.
    """

    inicio = time.monotonic()

    resultado_link = DocumentLinkEngine(limite_candidatos=limite_candidatos).executar()
    payload_link = resultado_link.as_dict()

    sync_km = _sincronizar_recebimento_documentokm()

    total_ld = DocumentoLD.objects.count()
    total_km = DocumentoKM.objects.count()
    total_transmittals = TransmittalKM.objects.count()

    ld_com_km = _contar_documentos_ld_com_km()
    revisoes_divergentes = _contar_revisoes_divergentes()
    score_baixo = _contar_score_baixo()
    score_medio = _score_medio_ld()

    sem_vinculo_km = max(total_ld - ld_com_km, 0)
    cobertura_ld_km = _percentual(ld_com_km, total_ld)

    status_km = list(
        DocumentoKM.objects.values("status_recebimento")
        .annotate(total=Count("id"))
        .order_by("-total", "status_recebimento")[:10]
    )

    por_disciplina = list(
        DocumentoKM.objects.values("disciplina")
        .annotate(total=Count("id"))
        .order_by("-total", "disciplina")[:10]
    )

    duracao_ms = int((time.monotonic() - inicio) * 1000)

    alertas_criticos = (
        revisoes_divergentes
        + payload_link.get("conflitos", 0)
        + payload_link.get("multiplos", 0)
    )

    return {
        "ok": True,
        "mensagem": (
            "Sync KM ↔ LD concluído: "
            f"{payload_link.get('processados', 0)} registros processados, "
            f"{payload_link.get('vinculados_auto', 0)} vínculos automáticos."
        ),
        "quantidade_processada": payload_link.get("processados", 0),
        "duracao_ms": duracao_ms,
        "link_engine": payload_link,
        "documento_km": sync_km,
        "kpis": {
            "total_ld": total_ld,
            "total_km": total_km,
            "total_transmittals": total_transmittals,
            "ld_com_km": ld_com_km,
            "sem_vinculo_km": sem_vinculo_km,
            "cobertura_ld_km": cobertura_ld_km,
            "revisoes_divergentes": revisoes_divergentes,
            "score_baixo": score_baixo,
            "score_medio": score_medio,
            "alertas_criticos": alertas_criticos,
        },
        "distribuicoes": {
            "status_km": status_km,
            "por_disciplina": por_disciplina,
        },
    }


def executar_sync_km_ld_job(*, user=None, payload: dict | None = None) -> dict[str, Any]:
    """
    Handler compatível com scheduler/job_manager.
    """

    limite = int((payload or {}).get("limite_candidatos") or 300)
    return executar_sync_km_ld(limite_candidatos=limite)
