"""
Importador real da Lista de Documentos Kongsberg/KM.

Entrada esperada:
- Planilha XLSX com aba "LD_KM"
- Cabeçalho normalmente na linha 2
- Coluna "Number" como chave mestre do DocumentoKM

Este service é propositalmente defensivo:
- ignora fórmulas quebradas como #NAME?
- usa introspecção de campos para evitar quebrar migrations antigas
- expõe aliases compatíveis: importar_ld_kongsberg e importar_lista_kongsberg
"""

from __future__ import annotations
import re
import time

from pathlib import Path
from typing import Any

from django.db import transaction
from django.db.models import Q
from openpyxl import load_workbook

from apps.automacoes.models import DocumentoKM, DocumentoLD, TransmittalKM


VALORES_INVALIDOS = {
    "#NAME?",
    "#VALUE!",
    "#REF!",
    "#DIV/0!",
    "#N/A",
    "#NULL!",
    "#NUM!",
}


COLUNAS_MAPEADAS = {
    "phase": "phase",
    "toc": "toc",
    "number": "numero_km",
    "title": "titulo",
    "discipline": "disciplina",
    "contractual delivery": "contractual_delivery",
    "preliminay delivery": "preliminary_delivery",
    "preliminary delivery": "preliminary_delivery",
    "agreed delivery": "agreed_delivery",
    "first delivery": "first_delivery",
    "released for": "released_for",
    "status": "status_km",
    "core share document": "core_share_document",
    "core share folder": "core_share_folder",
    "transmittal number": "transmittal_numero",
    "data recebimento km": "data_recebimento_km",
    "numero documento tp": "documento_tp",
    "número documento tp": "documento_tp",
    "documento tp": "documento_tp",
    "document tp": "documento_tp",
    "tp": "documento_tp",
    "numero tp": "documento_tp",
    "número tp": "documento_tp",
    "num documento tp": "documento_tp",
    "nº documento tp": "documento_tp",
    "no documento tp": "documento_tp",
}


def _texto(valor: Any) -> str:
    if valor is None:
        return ""

    texto = str(valor).strip()

    if not texto:
        return ""

    if texto.upper() in VALORES_INVALIDOS:
        return ""

    if texto.startswith("="):
        return ""

    return texto


def _normalizar_chave(valor: Any) -> str:
    texto = _texto(valor).lower()
    texto = texto.replace("\n", " ").replace("\r", " ")
    texto = " ".join(texto.split())
    return texto



def _texto_limpo(valor: Any) -> str:
    texto = _texto(valor).upper()
    texto = texto.replace("\\", "/").split("/")[-1]
    texto = texto.replace("_", "-")
    texto = " ".join(texto.split())
    return texto.strip()


def _compactar_documento(valor: Any) -> str:
    return "".join(ch for ch in _texto_limpo(valor) if ch.isalnum())


def _tokens_documento(valor: Any) -> list[str]:
    texto = _texto_limpo(valor)
    return [t for t in re.split(r"[^A-Z0-9]+", texto) if t]


def _remover_revisao_compacta(valor: str) -> str:
    texto = str(valor or "").upper()
    texto = re.sub(r"(REV|REVISAO|REVISÃO|R)[A-Z0-9]{1,3}$", "", texto)
    texto = re.sub(r"[A-Z]$", "", texto) if len(texto) > 10 else texto
    return texto


def _score_documental(km_valor: Any, ld_valor: Any) -> int:
    km = _compactar_documento(km_valor)
    ld = _compactar_documento(ld_valor)

    if not km or not ld:
        return 0

    if km == ld:
        return 100

    km_sem_rev = _remover_revisao_compacta(km)
    ld_sem_rev = _remover_revisao_compacta(ld)

    if km_sem_rev and ld_sem_rev and km_sem_rev == ld_sem_rev:
        return 96

    if len(km_sem_rev) >= 8 and km_sem_rev in ld_sem_rev:
        return 88

    if len(ld_sem_rev) >= 8 and ld_sem_rev in km_sem_rev:
        return 84

    km_tokens = _tokens_documento(km_valor)
    ld_texto = _texto_limpo(ld_valor)
    ld_compacto = _compactar_documento(ld_valor)

    tokens_relevantes = [t for t in km_tokens if len(t) >= 2]

    if tokens_relevantes:
        hits_texto = sum(1 for t in tokens_relevantes if t in ld_texto)
        hits_compacto = sum(1 for t in tokens_relevantes if t in ld_compacto)
        cobertura = max(hits_texto, hits_compacto) / max(len(tokens_relevantes), 1)

        if cobertura >= 1:
            return 76

        if cobertura >= 0.75 and len(tokens_relevantes) >= 4:
            return 68

    km_numeros = re.findall(r"\d+", _texto_limpo(km_valor))
    ld_numeros = re.findall(r"\d+", _texto_limpo(ld_valor))

    if km_numeros and ld_numeros:
        comuns = set(km_numeros).intersection(ld_numeros)
        if len(comuns) >= 3:
            return 64
        if len(comuns) >= 2 and any(len(n) >= 3 for n in comuns):
            return 58

    return 0


def _model_has_field(model, nome: str) -> bool:
    return any(field.name == nome for field in model._meta.get_fields())


def _detectar_aba(workbook):
    if "LD_KM" in workbook.sheetnames:
        return workbook["LD_KM"]

    for nome in workbook.sheetnames:
        if nome.strip().lower() in {"ld km", "ld_km", "document list", "documentos km"}:
            return workbook[nome]

    return workbook.active


def _detectar_cabecalho(sheet) -> tuple[int, dict[str, int]]:
    """
    Procura uma linha de cabeçalho contendo pelo menos Number e Title.
    Retorna: (linha_cabecalho, mapa_coluna_normalizada_para_indice_1_based)
    """
    melhor_linha = 1
    melhor_mapa = {}

    for row_idx in range(1, min(sheet.max_row, 15) + 1):
        mapa = {}

        for col_idx in range(1, sheet.max_column + 1):
            chave = _normalizar_chave(sheet.cell(row=row_idx, column=col_idx).value)
            if chave:
                mapa[chave] = col_idx

        score = 0
        if "number" in mapa:
            score += 3
        if "title" in mapa:
            score += 2
        if "discipline" in mapa:
            score += 1

        if score > len(melhor_mapa):
            melhor_linha = row_idx
            melhor_mapa = mapa

        if "number" in mapa and "title" in mapa:
            return row_idx, mapa

    return melhor_linha, melhor_mapa


def _valor_linha(sheet, row_idx: int, colunas: dict[str, int], nome_coluna: str) -> str:
    col_idx = colunas.get(nome_coluna)
    if not col_idx:
        return ""
    return _texto(sheet.cell(row=row_idx, column=col_idx).value)


def _montar_defaults(sheet, row_idx: int, colunas: dict[str, int], origem_planilha: str) -> dict:
    defaults = {}

    for coluna_origem, campo_model in COLUNAS_MAPEADAS.items():
        if campo_model == "numero_km":
            continue

        if not _model_has_field(DocumentoKM, campo_model):
            continue

        valor = _valor_linha(sheet, row_idx, colunas, coluna_origem)

        # Várias colunas/aliases podem apontar para o mesmo campo do model.
        # Não deixe um alias ausente/vazio sobrescrever um valor já encontrado.
        if campo_model in defaults and defaults[campo_model] and not valor:
            continue

        if campo_model not in defaults or valor:
            defaults[campo_model] = valor

    if _model_has_field(DocumentoKM, "origem_planilha"):
        defaults["origem_planilha"] = origem_planilha

    if _model_has_field(DocumentoKM, "linha_origem"):
        defaults["linha_origem"] = row_idx

    return defaults



def _emitir_progresso(callback, etapa: str, mensagem: str, percentual: int | None = None, **detalhes) -> None:
    """
    Emite progresso operacional sem acoplar o service à camada de views.

    - Se callback existir, envia payload estruturado.
    - Também imprime no terminal para acompanhamento durante imports longos.
    - Não deixa falha de callback interromper a importação.
    """
    payload = {
        "etapa": etapa,
        "mensagem": mensagem,
        "percentual": percentual,
        "detalhes": detalhes,
    }

    prefixo = f"[LD_KONGSBERG][{etapa}]"
    sufixo = f" ({percentual}%)" if percentual is not None else ""

    try:
        print(f"{prefixo} {mensagem}{sufixo}", flush=True)
    except Exception:
        pass

    if not callback:
        return

    try:
        callback(payload)
    except Exception:
        # Progresso nunca pode quebrar a rotina principal.
        pass

def importar_lista_kongsberg(
    arquivo,
    usuario=None,
    origem_planilha: str | None = None,
    nome_arquivo: str | None = None,
    progress_callback=None,
    executar_cruzamento: bool = False,
    **kwargs,
) -> dict:
    """
    Importa a LD Kongsberg para DocumentoKM.

    Compatível com chamadas antigas e com execução operacional assistida:
    - aceita caminho string/path, UploadedFile ou file-like object;
    - emite progresso por callback e no terminal;
    - opcionalmente executa o cruzamento KM ↔ LD ao final quando
      executar_cruzamento=True.
    """
    inicio = time.monotonic()
    origem = origem_planilha or nome_arquivo or getattr(arquivo, "name", "") or str(arquivo)

    _emitir_progresso(
        progress_callback,
        "INICIO",
        f"Iniciando importação da LD Kongsberg: {origem}",
        1,
        origem=origem,
    )

    if hasattr(arquivo, "seek"):
        try:
            arquivo.seek(0)
        except Exception:
            pass

    _emitir_progresso(progress_callback, "LEITURA_XLSX", "Abrindo planilha XLSX.", 5)

    wb = load_workbook(arquivo, data_only=True, read_only=True)
    sheet = _detectar_aba(wb)
    header_row, colunas = _detectar_cabecalho(sheet)

    _emitir_progresso(
        progress_callback,
        "CABECALHO",
        f"Aba '{sheet.title}' detectada. Cabeçalho na linha {header_row}.",
        10,
        aba=sheet.title,
        linha_cabecalho=header_row,
    )

    if "number" not in colunas:
        try:
            wb.close()
        except Exception:
            pass

        return {
            "ok": False,
            "mensagem": "Coluna obrigatória 'Number' não encontrada na LD Kongsberg.",
            "aba": sheet.title,
            "linha_cabecalho": header_row,
            "processados": 0,
            "criados": 0,
            "atualizados": 0,
            "ignorados": 0,
            "duracao_segundos": round(time.monotonic() - inicio, 3),
        }

    total_linhas_estimado = max((sheet.max_row or 0) - header_row, 0)
    processados = 0
    criados = 0
    atualizados = 0
    ignorados = 0
    erros = []

    _emitir_progresso(
        progress_callback,
        "IMPORTACAO",
        f"Importando registros da planilha ({total_linhas_estimado} linhas estimadas).",
        15,
        total_linhas_estimado=total_linhas_estimado,
    )

    try:
        with transaction.atomic():
            for row_idx in range(header_row + 1, sheet.max_row + 1):
                numero_km = _valor_linha(sheet, row_idx, colunas, "number")

                if not numero_km:
                    ignorados += 1
                    continue

                defaults = _montar_defaults(sheet, row_idx, colunas, origem)

                try:
                    _, created = DocumentoKM.objects.update_or_create(
                        numero_km=numero_km,
                        defaults=defaults,
                    )
                    processados += 1

                    if created:
                        criados += 1
                    else:
                        atualizados += 1

                except Exception as exc:
                    erros.append(
                        {
                            "linha": row_idx,
                            "numero_km": numero_km,
                            "erro": str(exc),
                        }
                    )

                if processados and processados % 100 == 0:
                    percentual = 15
                    if total_linhas_estimado:
                        percentual = min(75, 15 + int((processados / total_linhas_estimado) * 60))

                    _emitir_progresso(
                        progress_callback,
                        "IMPORTACAO",
                        (
                            f"{processados} processados, {criados} criados, "
                            f"{atualizados} atualizados, {ignorados} ignorados."
                        ),
                        percentual,
                        processados=processados,
                        criados=criados,
                        atualizados=atualizados,
                        ignorados=ignorados,
                        erros=len(erros),
                    )
    finally:
        try:
            wb.close()
        except Exception:
            pass

    resultado = {
        "ok": not erros,
        "mensagem": (
            f"LD Kongsberg importada: {processados} processados, "
            f"{criados} criados, {atualizados} atualizados, {ignorados} ignorados."
        ),
        "aba": sheet.title,
        "linha_cabecalho": header_row,
        "processados": processados,
        "criados": criados,
        "atualizados": atualizados,
        "ignorados": ignorados,
        "erros": erros[:20],
        "total_erros": len(erros),
        "quantidade_processada": processados,
        "duracao_segundos": round(time.monotonic() - inicio, 3),
    }

    _emitir_progresso(
        progress_callback,
        "IMPORTACAO_CONCLUIDA",
        resultado["mensagem"],
        80,
        processados=processados,
        criados=criados,
        atualizados=atualizados,
        ignorados=ignorados,
        erros=len(erros),
    )

    if executar_cruzamento:
        _emitir_progresso(
            progress_callback,
            "CRUZAMENTO",
            "Executando cruzamento operacional KM ↔ LD.",
            85,
        )

        cruzamento = executar_cruzamento_ld_km(progress_callback=progress_callback)
        resultado["cruzamento"] = cruzamento

        if not cruzamento.get("ok"):
            resultado["ok"] = False

        resultado["mensagem"] = (
            f"{resultado['mensagem']} "
            f"{cruzamento.get('mensagem', 'Cruzamento executado.')}"
        )

    resultado["duracao_segundos"] = round(time.monotonic() - inicio, 3)

    _emitir_progresso(
        progress_callback,
        "FIM",
        f"Rotina LD Kongsberg finalizada em {resultado['duracao_segundos']}s.",
        100,
        duracao_segundos=resultado["duracao_segundos"],
    )

    return resultado


def importar_ld_kongsberg(*args, **kwargs) -> dict:
    """Alias de compatibilidade usado por views existentes."""
    return importar_lista_kongsberg(*args, **kwargs)


def _buscar_transmittal_para_km(numero_km: str):
    compacto = _compactar_documento(numero_km)
    if not compacto:
        return None

    candidatos = TransmittalKM.objects.exclude(documento="").order_by("-id")[:5000]

    for item in candidatos:
        if _compactar_documento(item.documento) == compacto:
            return item

    for item in candidatos:
        doc_compacto = _compactar_documento(item.documento)
        if compacto and (compacto in doc_compacto or doc_compacto in compacto):
            return item

    return None



def _buscar_ld_para_km(numero_km: str):
    campos = [
        "numero_documento_km",
        "documento",
        "titulo",
        "caminho_documento",
        "caminho_grd",
        "caminho_pcf",
        "caminho_resposta",
        "caminho_grd_resposta",
    ]

    numero_km_txt = _texto(numero_km)
    numero_km_compacto = _compactar_documento(numero_km)

    if not numero_km_compacto:
        return None, 0

    query = Q()

    for campo in campos:
        if not _model_has_field(DocumentoLD, campo):
            continue

        query |= Q(**{f"{campo}__icontains": numero_km_txt})

        for token in _tokens_documento(numero_km_txt):
            if len(token) >= 4:
                query |= Q(**{f"{campo}__icontains": token})

    candidatos = list(DocumentoLD.objects.filter(query).distinct().order_by("-id")[:1200]) if query else []

    if not candidatos:
        candidatos = list(DocumentoLD.objects.exclude(documento="").order_by("-id")[:3000])

    melhor = None
    melhor_score = 0

    for item in candidatos:
        for campo in campos:
            if not _model_has_field(DocumentoLD, campo):
                continue

            valor = getattr(item, campo, "")
            score = _score_documental(numero_km_txt, valor)

            if campo == "numero_documento_km":
                score += 8 if score else 0
            elif campo == "documento":
                score += 5 if score else 0

            if score > melhor_score:
                melhor = item
                melhor_score = min(score, 100)

            if melhor_score >= 96:
                return melhor, melhor_score

    return melhor, melhor_score


def executar_cruzamento_ld_km(limite: int | None = None, progress_callback=None) -> dict:
    """
    Sincronização segura da Lista KM.

    Regra atual:
    - LD_KM é a fonte oficial da lista.
    - Documento TP NUNCA é inferido por similaridade.
    - Documento TP importado da planilha é preservado.
    - Recebimento é derivado de Transmittal Number ou Data recebimento KM.
    """
    inicio = time.monotonic()
    _emitir_progresso(progress_callback, "CRUZAMENTO", "Preparando documentos KM para sincronização.", 86)

    qs = DocumentoKM.objects.all().order_by("numero_km")
    total_estimado = DocumentoKM.objects.count()
    if limite:
        total_estimado = min(total_estimado, int(limite))
        qs = qs[: int(limite)]

    processados = 0
    recebidos = 0
    nao_recebidos = 0
    com_tp = 0
    sem_tp = 0

    for doc_km in qs:
        update_fields = []

        transmittal_numero = _texto(getattr(doc_km, "transmittal_numero", ""))
        data_recebimento = _texto(getattr(doc_km, "data_recebimento_km", ""))
        documento_tp = _texto(getattr(doc_km, "documento_tp", ""))

        recebido = bool(transmittal_numero or data_recebimento)

        if recebido:
            recebidos += 1
            if _model_has_field(DocumentoKM, "status_recebimento"):
                doc_km.status_recebimento = DocumentoKM.STATUS_RECEBIMENTO_RECEBIDO
                update_fields.append("status_recebimento")
        else:
            nao_recebidos += 1
            if _model_has_field(DocumentoKM, "status_recebimento"):
                doc_km.status_recebimento = DocumentoKM.STATUS_RECEBIMENTO_PENDENTE
                update_fields.append("status_recebimento")

        if documento_tp:
            com_tp += 1
            if _model_has_field(DocumentoKM, "status_vinculo_ld"):
                doc_km.status_vinculo_ld = DocumentoKM.STATUS_VINCULO_LD_AUTO
                update_fields.append("status_vinculo_ld")
        else:
            sem_tp += 1
            if _model_has_field(DocumentoKM, "status_vinculo_ld"):
                doc_km.status_vinculo_ld = DocumentoKM.STATUS_VINCULO_LD_SEM_MATCH
                update_fields.append("status_vinculo_ld")

        # Não atualiza documento_tp, documento_ld ou score_vinculo_ld.
        # Esses campos não devem ser preenchidos por fuzzy/similaridade.

        if update_fields:
            if _model_has_field(DocumentoKM, "atualizado_em"):
                update_fields.append("atualizado_em")
            doc_km.save(update_fields=sorted(set(update_fields)))

        processados += 1

        if processados and processados % 500 == 0:
            percentual = 86
            if total_estimado:
                percentual = min(98, 86 + int((processados / total_estimado) * 12))
            _emitir_progresso(
                progress_callback,
                "CRUZAMENTO",
                f"{processados} documentos KM sincronizados.",
                percentual,
                processados=processados,
                recebidos=recebidos,
                nao_recebidos=nao_recebidos,
                com_tp=com_tp,
                sem_tp=sem_tp,
            )

    duracao_cruzamento = round(time.monotonic() - inicio, 3)
    _emitir_progresso(
        progress_callback,
        "CRUZAMENTO_CONCLUIDO",
        f"Cruzamento KM ↔ LD seguro concluído em {duracao_cruzamento}s.",
        99,
        processados=processados,
        recebidos=recebidos,
        nao_recebidos=nao_recebidos,
        com_tp=com_tp,
        sem_tp=sem_tp,
    )

    return {
        "ok": True,
        "mensagem": (
            f"Sincronização KM segura concluída: {processados} processados, "
            f"{recebidos} recebidos, {nao_recebidos} não recebidos, "
            f"{com_tp} com Documento TP importado."
        ),
        "processados": processados,
        "recebidos": recebidos,
        "nao_recebidos": nao_recebidos,
        "pendentes_recebimento": nao_recebidos,
        "tp_importado_ld_km": com_tp,
        "com_documento_tp": com_tp,
        "sem_documento_tp": sem_tp,
        "vinculados_ld": com_tp,
        "sem_vinculo_ld": sem_tp,
        "quantidade_processada": processados,
        "duracao_segundos": duracao_cruzamento,
    }


# Alias adicional para scheduler/jobs futuros.
executar_cruzamento_km_ld = executar_cruzamento_ld_km
