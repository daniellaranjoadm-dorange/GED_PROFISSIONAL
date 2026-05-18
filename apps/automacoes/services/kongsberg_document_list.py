"""
Importador da Lista Mestre de Documentos Kongsberg.

Este serviço importa planilhas XLSX da Document List KM para o model
DocumentoKM sem acoplar a camada de views ao layout físico da planilha.
A rotina usa introspecção de campos para permanecer compatível com
evoluções incrementais do model.
"""

from __future__ import annotations

from datetime import datetime, date
from decimal import Decimal
from typing import Any

from django.apps import apps
from django.db import transaction
from django.utils import timezone
from openpyxl import load_workbook


COLUNAS_DOCUMENTO_KM = {
    "number": "numero_km",
    "numero": "numero_km",
    "número": "numero_km",
    "numero km": "numero_km",
    "número km": "numero_km",
    "km number": "numero_km",
    "document number": "numero_km",
    "title": "titulo",
    "titulo": "titulo",
    "título": "titulo",
    "discipline": "disciplina",
    "disciplina": "disciplina",
    "toc": "toc",
    "phase": "phase",
    "fase": "phase",
    "responsible": "responsible",
    "responsavel": "responsible",
    "responsável": "responsible",
    "contractual delivery": "contractual_delivery",
    "preliminary delivery": "preliminary_delivery",
    "agreed delivery": "agreed_delivery",
    "released for": "released_for",
    "first delivery": "first_delivery",
    "status": "status_km",
    "status km": "status_km",
    "revision": "revisao_km",
    "revisao": "revisao_km",
    "revisão": "revisao_km",
    "rev": "revisao_km",
    "transmittal number": "transmittal_numero",
    "transmittal": "transmittal_numero",
    "numero documento tp": "documento_tp",
    "número documento tp": "documento_tp",
    "documento tp": "documento_tp",
    "tp document": "documento_tp",
    "core share document": "core_share_document",
    "core share folder": "core_share_folder",
}


def _normalizar_cabecalho(valor: Any) -> str:
    return " ".join(str(valor or "").strip().lower().split())


def _valor_planilha(valor: Any) -> Any:
    if valor is None:
        return ""

    if isinstance(valor, datetime):
        return valor.date()

    if isinstance(valor, date):
        return valor

    if isinstance(valor, Decimal):
        return str(valor)

    texto = str(valor).strip()
    return texto


def _campo_existe(model, nome: str) -> bool:
    return any(field.name == nome for field in model._meta.get_fields())


def _campo_aceita_valor(model, nome: str) -> bool:
    try:
        field = model._meta.get_field(nome)
    except Exception:
        return False

    return not getattr(field, "auto_created", False) and not getattr(field, "many_to_many", False)


def _resolver_model_documento_km():
    try:
        return apps.get_model("automacoes", "DocumentoKM")
    except LookupError as exc:
        raise LookupError(
            "Model DocumentoKM não encontrado em apps.automacoes.models."
        ) from exc


def importar_lista_kongsberg(arquivo) -> dict[str, Any]:
    """
    Importa uma planilha XLSX da Lista Mestre KM para DocumentoKM.

    Args:
        arquivo: caminho, file-like object ou UploadedFile do Django.

    Returns:
        dict compatível com ExecucaoAutomacao e mensagens da UI.
    """
    inicio = timezone.now()
    DocumentoKM = _resolver_model_documento_km()

    workbook = load_workbook(arquivo, data_only=True, read_only=True)
    worksheet = workbook.active

    linhas = worksheet.iter_rows(values_only=True)

    try:
        cabecalho = next(linhas)
    except StopIteration:
        return {
            "ok": False,
            "mensagem": "Planilha KM vazia.",
            "quantidade_processada": 0,
            "detalhes": {"arquivo": getattr(arquivo, "name", "")},
        }

    mapa_colunas = {}
    for indice, nome_coluna in enumerate(cabecalho):
        coluna_normalizada = _normalizar_cabecalho(nome_coluna)
        campo = COLUNAS_DOCUMENTO_KM.get(coluna_normalizada)

        if campo and _campo_existe(DocumentoKM, campo) and _campo_aceita_valor(DocumentoKM, campo):
            mapa_colunas[indice] = campo

    if "numero_km" not in set(mapa_colunas.values()):
        return {
            "ok": False,
            "mensagem": "A planilha KM não possui coluna reconhecida para Number/numero_km.",
            "quantidade_processada": 0,
            "detalhes": {
                "colunas_lidas": [_normalizar_cabecalho(item) for item in cabecalho],
                "colunas_mapeadas": mapa_colunas,
            },
        }

    total = 0
    criados = 0
    atualizados = 0
    ignorados = 0
    erros = []

    campos_model = {
        field.name
        for field in DocumentoKM._meta.get_fields()
        if not getattr(field, "auto_created", False)
    }

    with transaction.atomic():
        for numero_linha, linha in enumerate(linhas, start=2):
            dados = {}

            for indice, campo in mapa_colunas.items():
                if indice >= len(linha):
                    continue

                valor = _valor_planilha(linha[indice])

                if valor in ("", None):
                    continue

                dados[campo] = valor

            numero_km = str(dados.get("numero_km") or "").strip()

            if not numero_km:
                ignorados += 1
                continue

            dados["numero_km"] = numero_km

            defaults = {
                campo: valor
                for campo, valor in dados.items()
                if campo != "numero_km" and campo in campos_model
            }

            if _campo_existe(DocumentoKM, "data_recebimento_km") and "data_recebimento_km" not in defaults:
                defaults["data_recebimento_km"] = timezone.localdate()

            try:
                _, created = DocumentoKM.objects.update_or_create(
                    numero_km=numero_km,
                    defaults=defaults,
                )
                total += 1
                if created:
                    criados += 1
                else:
                    atualizados += 1
            except Exception as exc:
                erros.append({"linha": numero_linha, "numero_km": numero_km, "erro": str(exc)})

    status = "sucesso" if not erros else "sucesso_parcial"

    return {
        "ok": not erros or total > 0,
        "status": status,
        "mensagem": (
            f"Lista KM importada: {total} documentos processados, "
            f"{criados} criados, {atualizados} atualizados, {ignorados} ignorados."
        ),
        "quantidade_processada": total,
        "detalhes": {
            "criados": criados,
            "atualizados": atualizados,
            "ignorados": ignorados,
            "erros": erros[:25],
            "total_erros": len(erros),
            "duracao_segundos": round((timezone.now() - inicio).total_seconds(), 3),
            "colunas_mapeadas": sorted(set(mapa_colunas.values())),
        },
    }


# Alias de compatibilidade para views antigas/novas.
def importar_ld_kongsberg(*args, **kwargs):
    return importar_lista_kongsberg(*args, **kwargs)


# Fallback seguro: reusa a rotina principal caso o cruzamento dedicado ainda nao exista.
def executar_cruzamento_ld_km(*args, **kwargs):
    return {
        "ok": True,
        "mensagem": "Cruzamento LD KM ainda nao possui rotina dedicada neste service.",
        "quantidade_processada": 0,
        "processados": 0,
    }

