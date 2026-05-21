
from pathlib import Path

from django.conf import settings
import os
import time
import traceback
import re

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.utils import timezone
from django.core.paginator import Paginator
from django.core.cache import cache
from django.db.models import Avg, Count, Q, Sum
from django.http import FileResponse, Http404, HttpResponse, JsonResponse
from django.http import HttpResponse
from django.shortcuts import redirect, render
from openpyxl import Workbook
from openpyxl.styles import Font, PatternFill

from apps.automacoes.models import TransmittalKM, PCFTimeline, DocumentoLD, DocumentoKM, ExecucaoAutomacao, KMFileIndex
from apps.automacoes.services import (
    atualizar_ld,
    grd_ghenova,
    timeline_pcfs,
    transmittal_km,
)
from apps.automacoes.services.ld_parser import extrair_tipo_documental
from apps.automacoes.services.ld_path_resolver import gerar_hyperlink_ld, resolver_caminho_ld
from apps.automacoes.services.status_normalizer import normalizar_status
from apps.automacoes.services.search_engine import buscar_global_enterprise
from apps.automacoes.services.search_analytics import obter_search_analytics
from apps.automacoes.services.km_index_jobs import executar_reindexacao_km_job
from apps.automacoes.services.ops_center_service import OperationsCenterService
from apps.automacoes.services.runtime_events import RuntimeEventStreamService
from apps.automacoes.services.runtime_health_api import RuntimeHealthAPIService
from apps.automacoes.services.runtime_retention import RuntimeRetentionService
from apps.automacoes.services.kongsberg_document_list import importar_ld_kongsberg, executar_cruzamento_ld_km



KM_DOCUMENTOS_BASE = Path(
    r"\\virm-rgr022\FILESERVER\Projetos\05_HANDYMAX\09. Doc Control\15 - Documentos KM"
)

KM_EXTENSOES_PRIORITARIAS = {
    ".docx": 60,
    ".doc": 58,
    ".dwg": 54,
    ".xlsx": 48,
    ".xlsm": 46,
    ".xls": 44,
    ".pdf": 20,
}


def _cache_ttl(nome, padrao):
    return int(getattr(settings, nome, padrao) or padrao)


def _cache_get_or_set(chave, builder, ttl):
    valor = cache.get(chave)
    if valor is not None:
        return valor

    valor = builder()
    cache.set(chave, valor, ttl)
    return valor




def _model_has_field(model, nome):
    return any(field.name == nome for field in model._meta.get_fields())


def _latest_model_value(model, *campos):
    for campo in campos:
        if _model_has_field(model, campo):
            try:
                valor = (
                    model.objects.exclude(**{f"{campo}__isnull": True})
                    .order_by(f"-{campo}")
                    .values_list(campo, flat=True)
                    .first()
                )
                if valor:
                    return valor
            except Exception:
                continue
    return None


def _extrair_quantidade_processada(resultado):
    if not isinstance(resultado, dict):
        return 0

    chaves = (
        "quantidade_processada",
        "processados",
        "total_processado",
        "total",
        "importados",
        "criados",
        "atualizados",
    )

    for chave in chaves:
        valor = resultado.get(chave)
        if isinstance(valor, int):
            return valor

    detalhes = resultado.get("detalhes")
    if isinstance(detalhes, dict):
        for chave in chaves:
            valor = detalhes.get(chave)
            if isinstance(valor, int):
                return valor

    return 0


def _detalhes_execucao(resultado):
    if not isinstance(resultado, dict):
        return {}

    detalhes = resultado.get("detalhes")
    if isinstance(detalhes, dict):
        return detalhes

    return {
        chave: valor
        for chave, valor in resultado.items()
        if chave not in {"ok", "mensagem"}
        and isinstance(valor, (str, int, float, bool, list, dict, type(None)))
    }


def _formatar_duracao(segundos):
    segundos = float(segundos or 0)

    if segundos < 60:
        return f"{segundos:.1f}s" if segundos and segundos < 10 else f"{round(segundos)}s"

    minutos = int(segundos // 60)
    resto = int(segundos % 60)
    return f"{minutos}m {resto}s"


def _health_automacoes(nomes):
    health = {}

    for nome in nomes:
        qs = ExecucaoAutomacao.objects.filter(nome=nome)
        ultima = qs.order_by("-iniciado_em").first()
        total_finalizado = qs.exclude(status=ExecucaoAutomacao.STATUS_INICIADO).count()
        total_sucesso = qs.filter(status=ExecucaoAutomacao.STATUS_SUCESSO).count()
        total_erros = qs.filter(status=ExecucaoAutomacao.STATUS_ERRO).count()
        duracao_media = (
            qs.exclude(duracao_segundos=0)
            .aggregate(media=Avg("duracao_segundos"))
            .get("media")
            or 0
        )

        if not ultima:
            estado = "OCIOSO"
            classe = "auto-status-idle"
            icone = "bi-circle"
        elif ultima.status == ExecucaoAutomacao.STATUS_INICIADO:
            estado = "EXECUTANDO"
            classe = "auto-status-running"
            icone = "bi-arrow-repeat"
        elif ultima.status == ExecucaoAutomacao.STATUS_ERRO:
            estado = "ERRO"
            classe = "auto-status-error"
            icone = "bi-exclamation-triangle"
        else:
            estado = "ONLINE"
            classe = "auto-status-online"
            icone = "bi-check-circle"

        taxa_sucesso = round((total_sucesso / total_finalizado) * 100, 1) if total_finalizado else 0

        health[nome] = {
            "estado": estado,
            "classe": classe,
            "icone": icone,
            "ultima": ultima,
            "taxa_sucesso": taxa_sucesso,
            "total_erros": total_erros,
            "duracao_media": round(duracao_media, 2) if duracao_media else 0,
            "duracao_media_fmt": _formatar_duracao(duracao_media),
        }

    return health



@login_required
def painel(request):
    def _build_painel_context():
        total_ld = DocumentoLD.objects.count()
        total_pcfs = PCFTimeline.objects.count()
        total_transmittals = TransmittalKM.objects.count()

        total_ld_com_pcf = 0
        if _model_has_field(DocumentoLD, "pcf"):
            total_ld_com_pcf = DocumentoLD.objects.exclude(pcf="").exclude(pcf__isnull=True).count()

        total_ld_sem_pcf = max(total_ld - total_ld_com_pcf, 0)

        total_pcfs_open = PCFTimeline.objects.filter(open_comments__gt=0).count()
        total_pcfs_not_released = PCFTimeline.objects.filter(status_final__iexact="NOT RELEASED").count()
        total_pcfs_released = PCFTimeline.objects.filter(status_final__iexact="RELEASED").count()

        total_transmittals_unicos = (
            TransmittalKM.objects.exclude(transmittal_numero="")
            .exclude(transmittal_numero__isnull=True)
            .values("transmittal_numero")
            .distinct()
            .count()
            if _model_has_field(TransmittalKM, "transmittal_numero")
            else 0
        )

        total_transmittals_sem_pdf = (
            TransmittalKM.objects.filter(Q(arquivo_pdf="") | Q(arquivo_pdf__isnull=True)).count()
            if _model_has_field(TransmittalKM, "arquivo_pdf")
            else 0
        )

        ultimos_pcfs = list(
            PCFTimeline.objects.order_by("-atualizado_em")[:5]
            if _model_has_field(PCFTimeline, "atualizado_em")
            else PCFTimeline.objects.all()[:5]
        )

        ultimos_transmittals = list(
            TransmittalKM.objects.order_by("-criado_em")[:5]
            if _model_has_field(TransmittalKM, "criado_em")
            else TransmittalKM.objects.all()[:5]
        )

        ultima_atualizacao = (
            _latest_model_value(PCFTimeline, "atualizado_em", "criado_em")
            or _latest_model_value(TransmittalKM, "criado_em", "atualizado_em")
            or _latest_model_value(DocumentoLD, "atualizado_em", "criado_em")
        )

        ultimas_execucoes = list(
            ExecucaoAutomacao.objects.select_related("usuario").order_by("-iniciado_em")[:8]
        )
        ultima_execucao = ultimas_execucoes[0] if ultimas_execucoes else None
        ultima_falha = (
            ExecucaoAutomacao.objects.select_related("usuario")
            .filter(sucesso=False)
            .exclude(status=ExecucaoAutomacao.STATUS_INICIADO)
            .order_by("-iniciado_em")
            .first()
        )

        total_execucoes = ExecucaoAutomacao.objects.count()
        total_falhas = (
            ExecucaoAutomacao.objects.filter(sucesso=False)
            .exclude(status=ExecucaoAutomacao.STATUS_INICIADO)
            .count()
        )
        total_sucessos = ExecucaoAutomacao.objects.filter(status=ExecucaoAutomacao.STATUS_SUCESSO).count()
        total_finalizados = ExecucaoAutomacao.objects.exclude(status=ExecucaoAutomacao.STATUS_INICIADO).count()
        taxa_sucesso_global = round((total_sucessos / total_finalizados) * 100, 1) if total_finalizados else 0

        hoje = timezone.localdate()
        execucoes_hoje = ExecucaoAutomacao.objects.filter(iniciado_em__date=hoje).count()
        falhas_hoje = ExecucaoAutomacao.objects.filter(
            iniciado_em__date=hoje,
            status=ExecucaoAutomacao.STATUS_ERRO,
        ).count()

        duracao_media_global = (
            ExecucaoAutomacao.objects.exclude(duracao_segundos=0)
            .aggregate(media=Avg("duracao_segundos"))
            .get("media")
            or 0
        )
        duracao_media_global = round(duracao_media_global, 2) if duracao_media_global else 0

        total_km_index = KMFileIndex.objects.filter(ativo=True).count()
        total_km_docs_index = KMFileIndex.objects.filter(ativo=True, eh_transmittal_letter=False).count()
        total_km_transmittals_index = KMFileIndex.objects.filter(ativo=True, eh_transmittal_letter=True).count()
        ultima_indexacao_km = (
            KMFileIndex.objects.filter(ativo=True)
            .order_by("-indexado_em")
            .values_list("indexado_em", flat=True)
            .first()
        )

        automacoes = [
            {
                "nome": "Atualização LD",
                "subtitulo": "Lista de Documentos",
                "icone": "bi-file-earmark-spreadsheet",
                "badge": "Crítica",
                "badge_class": "auto-badge-warning",
                "descricao": "Sincroniza dados documentais, revisões, PCFs, GRDs, links de rede e medição.",
                "form_url": "automacoes:atualizar_ld",
                "botao": "Executar Atualização LD",
                "botao_class": "btn-primary",
                "dashboard_url": "automacoes:dashboard_ld",
                "registros_url": "automacoes:lista_ld",
                "metricas": [
                    {"label": "Linhas LD", "valor": total_ld},
                    {"label": "Com PCF", "valor": total_ld_com_pcf},
                    {"label": "Sem PCF", "valor": total_ld_sem_pcf},
                ],
            },
            {
                "nome": "Timeline PCFs",
                "subtitulo": "Comentários e revisões",
                "icone": "bi-bar-chart-line",
                "badge": "Integrada",
                "badge_class": "auto-badge-success",
                "descricao": "Gera e atualiza a timeline das PCFs recebidas e respondidas.",
                "form_url": "automacoes:timeline_pcfs",
                "botao": "Gerar Timeline PCFs",
                "botao_class": "btn-success",
                "dashboard_url": "automacoes:dashboard_pcfs",
                "registros_url": "automacoes:pcfs_timeline",
                "metricas": [
                    {"label": "PCFs", "valor": total_pcfs},
                    {"label": "Open", "valor": total_pcfs_open},
                    {"label": "Not Released", "valor": total_pcfs_not_released},
                ],
            },
            {
                "nome": "Transmittal KM",
                "subtitulo": "Parser PDF",
                "icone": "bi-box-seam",
                "badge": "Parser PDF",
                "badge_class": "auto-badge-info",
                "descricao": "Lê PDFs KM e consolida transmittals para acompanhamento documental.",
                "form_url": "automacoes:transmittal_km",
                "botao": "Consolidar Transmittals KM",
                "botao_class": "btn-info",
                "dashboard_url": "automacoes:dashboard_transmittals",
                "registros_url": "automacoes:transmittals_km",
                "metricas": [
                    {"label": "Registros", "valor": total_transmittals},
                    {"label": "Transmittals", "valor": total_transmittals_unicos},
                    {"label": "Sem PDF", "valor": total_transmittals_sem_pdf},
                ],
            },
            {
                "nome": "Índice KM",
                "subtitulo": "Arquivos e documentos KM",
                "icone": "bi-hdd-network",
                "badge": "Indexação",
                "badge_class": "auto-badge-info",
                "descricao": "Varre a pasta Documentos KM, indexa arquivos técnicos e acelera a abertura direta dos documentos.",
                "form_url": "automacoes:indexar_km",
                "botao": "Atualizar Índice KM",
                "botao_class": "btn-primary",
                "dashboard_url": "automacoes:transmittals_km",
                "registros_url": "automacoes:transmittals_km",
                "metricas": [
                    {"label": "Arquivos", "valor": total_km_index},
                    {"label": "Docs técnicos", "valor": total_km_docs_index},
                    {"label": "Letters", "valor": total_km_transmittals_index},
                ],
            },
            {
                "nome": "GRD GHENOVA",
                "subtitulo": "Consolidação GRDs 7K e 14K",
                "icone": "bi-diagram-3",
                "badge": "Engenharia",
                "badge_class": "auto-badge-neutral",
                "descricao": "Processa PDFs de GRD e gera planilhas consolidadas por empreendimento.",
                "form_url": "automacoes:grd_ghenova",
                "botao": "Consolidar GRDs GHENOVA",
                "botao_class": "btn-secondary",
                "dashboard_url": "",
                "registros_url": "",
                "metricas": [
                    {"label": "Fonte", "valor": "PDF"},
                    {"label": "Escopo", "valor": "7K/14K"},
                    {"label": "Status", "valor": "Ativo"},
                ],
            },
        ]

        health_map = _health_automacoes([rotina["nome"] for rotina in automacoes])
        for rotina in automacoes:
            rotina["health"] = health_map.get(rotina["nome"], {})

        return {
            "total_ld": total_ld,
            "total_pcfs": total_pcfs,
            "total_pcfs_open": total_pcfs_open,
            "total_pcfs_released": total_pcfs_released,
            "total_pcfs_not_released": total_pcfs_not_released,
            "total_transmittals": total_transmittals,
            "total_transmittals_unicos": total_transmittals_unicos,
            "ultima_atualizacao": ultima_atualizacao,
            "automacoes": automacoes,
            "ultimos_pcfs": ultimos_pcfs,
            "ultimos_transmittals": ultimos_transmittals,
            "ultimas_execucoes": ultimas_execucoes,
            "ultima_execucao": ultima_execucao,
            "ultima_falha": ultima_falha,
            "total_execucoes": total_execucoes,
            "total_falhas": total_falhas,
            "total_sucessos": total_sucessos,
            "taxa_sucesso_global": taxa_sucesso_global,
            "execucoes_hoje": execucoes_hoje,
            "falhas_hoje": falhas_hoje,
            "duracao_media_global": duracao_media_global,
            "total_km_index": total_km_index,
            "total_km_docs_index": total_km_docs_index,
            "total_km_transmittals_index": total_km_transmittals_index,
            "ultima_indexacao_km": ultima_indexacao_km,
        }

    context = _cache_get_or_set(
        "automacoes:painel:context:v1",
        _build_painel_context,
        _cache_ttl("CACHE_TTL_SHORT", 60),
    )

    return render(request, "automacoes/painel.html", context)


def _executar_automacao(request, executor, nome):
    if request.method != "POST":
        messages.error(request, f"Método inválido para executar {nome}.")
        return redirect("automacoes:painel")

    inicio = time.monotonic()
    log = ExecucaoAutomacao.objects.create(
        nome=nome,
        usuario=request.user if request.user.is_authenticated else None,
        status=ExecucaoAutomacao.STATUS_INICIADO,
        mensagem="Execução iniciada.",
    )

    try:
        resultado = executor()
        ok = bool(resultado.get("ok")) if isinstance(resultado, dict) else False
        mensagem = (
            resultado.get("mensagem")
            if isinstance(resultado, dict)
            else f"{nome} executado."
        )

        log.status = ExecucaoAutomacao.STATUS_SUCESSO if ok else ExecucaoAutomacao.STATUS_ERRO
        log.sucesso = ok
        log.mensagem = mensagem or (
            f"{nome} executado com sucesso." if ok else f"Falha ao executar {nome}."
        )
        log.quantidade_processada = _extrair_quantidade_processada(resultado)
        log.detalhes = _detalhes_execucao(resultado)

        if ok:
            messages.success(request, log.mensagem)
        else:
            messages.error(request, log.mensagem)

    except Exception as exc:
        log.status = ExecucaoAutomacao.STATUS_ERRO
        log.sucesso = False
        log.mensagem = f"Erro ao executar {nome}: {exc}"
        log.detalhes = {"erro": str(exc)}
        messages.error(request, log.mensagem)

    finally:
        log.finalizado_em = timezone.now()
        log.duracao_segundos = round(time.monotonic() - inicio, 3)
        log.save(
            update_fields=[
                "status",
                "sucesso",
                "mensagem",
                "detalhes",
                "quantidade_processada",
                "duracao_segundos",
                "finalizado_em",
            ]
        )
        cache.delete("automacoes:painel:context:v1")

    return redirect("automacoes:painel")


@login_required
def logs_automacoes(request):
    busca = request.GET.get("q", "").strip()
    tipo_doc = request.GET.get("tipo_doc", "").strip().upper()

    tipos_documentais = [
        "AC", "AF", "AP", "AR", "AV", "BM", "BS", "CA", "CC", "CE", "CF", "CG",
        "CI", "CL", "CM", "CO", "CP", "CQ", "CR", "CT", "CV", "DB", "DC", "DE",
        "DF", "DI", "DL", "DO", "DR", "DT", "DU", "EE", "EC", "EM", "ES", "ET",
        "EQ", "FD", "GE", "GI", "ID", "IT", "IS", "LA", "LC", "LD", "LE", "LI",
        "LM", "LP", "LO", "LV", "LT", "MA", "MC", "MD", "MG", "MI", "ML", "MM",
        "MO", "NA", "NC", "NF", "NP", "NQ", "NT", "OA", "OC", "OG", "OS", "PC",
        "PE", "PG", "PI", "PJ", "PL", "PM", "PO", "PP", "PQ", "PR", "PT", "QT",
        "RA", "RC", "RD", "RE", "RH", "RL", "RM", "RV", "SC", "SM", "SP", "TF",
        "TI", "TP", "TR",
    ]

    status = request.GET.get("status", "").strip()
    nome = request.GET.get("nome", "").strip()

    logs = ExecucaoAutomacao.objects.select_related("usuario").order_by("-iniciado_em")

    if busca:
        logs = logs.filter(
            Q(nome__icontains=busca)
            | Q(mensagem__icontains=busca)
            | Q(usuario__username__icontains=busca)
            | Q(usuario__first_name__icontains=busca)
            | Q(usuario__last_name__icontains=busca)
        )

    if status:
        logs = logs.filter(status=status)

    if nome:
        logs = logs.filter(nome__iexact=nome)

    nomes = (
        ExecucaoAutomacao.objects.exclude(nome="")
        .values_list("nome", flat=True)
        .distinct()
        .order_by("nome")
    )

    total = logs.count()
    total_sucesso = logs.filter(sucesso=True).count()
    total_erros = logs.filter(status=ExecucaoAutomacao.STATUS_ERRO).count()
    total_iniciados = logs.filter(status=ExecucaoAutomacao.STATUS_INICIADO).count()

    duracao_media = logs.exclude(duracao_segundos=0).aggregate(
        media=Avg("duracao_segundos")
    ).get("media")
    duracao_media = round(duracao_media, 2) if duracao_media else 0

    total_finalizados = logs.exclude(status=ExecucaoAutomacao.STATUS_INICIADO).count()
    taxa_sucesso = round((total_sucesso / total_finalizados) * 100, 1) if total_finalizados else 0
    hoje = timezone.localdate()
    falhas_hoje = logs.filter(iniciado_em__date=hoje, status=ExecucaoAutomacao.STATUS_ERRO).count()
    execucoes_hoje = logs.filter(iniciado_em__date=hoje).count()

    por_automacao = list(
        logs.values("nome")
        .annotate(total=Count("id"))
        .order_by("-total", "nome")[:10]
    )
    automacao_chart_labels = [(item.get("nome") or "Sem nome") for item in por_automacao]
    automacao_chart_values = [item.get("total") or 0 for item in por_automacao]

    erros_por_automacao = list(
        logs.filter(status=ExecucaoAutomacao.STATUS_ERRO)
        .values("nome")
        .annotate(total=Count("id"))
        .order_by("-total", "nome")[:10]
    )
    erros_chart_labels = [(item.get("nome") or "Sem nome") for item in erros_por_automacao]
    erros_chart_values = [item.get("total") or 0 for item in erros_por_automacao]

    paginator = Paginator(logs, 50)
    page_obj = paginator.get_page(request.GET.get("page"))

    return render(
        request,
        "automacoes/logs_automacoes.html",
        {
            "logs": page_obj,
            "page_obj": page_obj,
            "busca": busca,
            "status": status,
            "nome": nome,
            "nomes": nomes,
            "total": total,
            "total_sucesso": total_sucesso,
            "total_erros": total_erros,
            "total_iniciados": total_iniciados,
            "duracao_media": duracao_media,
            "taxa_sucesso": taxa_sucesso,
            "falhas_hoje": falhas_hoje,
            "execucoes_hoje": execucoes_hoje,
            "automacao_chart_labels": automacao_chart_labels,
            "automacao_chart_values": automacao_chart_values,
            "erros_chart_labels": erros_chart_labels,
            "erros_chart_values": erros_chart_values,
            "status_choices": ExecucaoAutomacao.STATUS_CHOICES,
        },
    )


@login_required
def executar_atualizar_ld(request):
    return _executar_automacao(
        request,
        atualizar_ld.executar,
        "Atualização LD",
    )


@login_required
def timeline_pcfs_view(request):
    return _executar_automacao(
        request,
        timeline_pcfs.executar,
        "Timeline PCFs",
    )


@login_required
def executar_transmittal_km(request):
    return _executar_automacao(
        request,
        transmittal_km.executar,
        "Transmittal KM",
    )


@login_required
def executar_grd_ghenova(request):
    return _executar_automacao(
        request,
        grd_ghenova.executar,
        "GRD GHENOVA",
    )


def _km_documento_extraido_do_nome(path):
    """
    Extrai um identificador documental provável do nome do arquivo KM.
    Mantém formato legível quando possível; a busca usa também campos normalizados.
    """
    stem = Path(path).stem
    stem = re.sub(r"[_]+", "-", stem)
    m = re.search(r"(\d{2}-\d{4}-\d{2}-\d{3,4}-\d{2,4}-\d{2}(?:-[A-Z0-9]+)?)", stem, re.IGNORECASE)
    if m:
        return m.group(1).upper()

    m = re.search(r"(\d{3,4}-\d{2,4}-\d{2}(?:-[A-Z0-9]+)?)", stem, re.IGNORECASE)
    if m:
        return m.group(1).upper()

    return ""


def _km_indexar_banco():
    """
    Varre a árvore KM e grava um índice persistente no banco.
    Isso evita varredura de rede a cada abertura de documento.
    """
    inicio = time.monotonic()

    if not KM_DOCUMENTOS_BASE.exists():
        return {
            "ok": False,
            "mensagem": f"Pasta KM não encontrada: {KM_DOCUMENTOS_BASE}",
            "quantidade_processada": 0,
            "detalhes": {"base": str(KM_DOCUMENTOS_BASE)},
        }

    KMFileIndex.objects.update(ativo=False)

    total = 0
    criados = 0
    atualizados = 0
    erros = 0
    por_extensao = {}

    for arquivo in KM_DOCUMENTOS_BASE.rglob("*"):
        try:
            if not arquivo.is_file():
                continue

            stat = arquivo.stat()
            extensao = arquivo.suffix.lower()
            por_extensao[extensao or "sem_extensao"] = por_extensao.get(extensao or "sem_extensao", 0) + 1

            defaults = {
                "nome_arquivo": arquivo.name,
                "pasta": str(arquivo.parent),
                "extensao": extensao,
                "tamanho_bytes": int(stat.st_size or 0),
                "modificado_em": timezone.datetime.fromtimestamp(
                    stat.st_mtime,
                    tz=timezone.get_current_timezone(),
                ),
                "nome_normalizado": _km_normalizar(arquivo.name),
                "stem_normalizado": _km_normalizar(arquivo.stem),
                "documento_extraido": _km_documento_extraido_do_nome(arquivo),
                "eh_transmittal_letter": _km_eh_transmittal_letter(arquivo),
                "ativo": True,
            }

            _, created = KMFileIndex.objects.update_or_create(
                caminho_completo=str(arquivo),
                defaults=defaults,
            )

            total += 1
            if created:
                criados += 1
            else:
                atualizados += 1

        except Exception:
            erros += 1
            continue

    _km_limpar_cache()

    removidos = KMFileIndex.objects.filter(ativo=False).count()
    status = "sucesso" if erros == 0 else "sucesso_parcial"

    return {
        "ok": True,
        "status": status,
        "mensagem": (
            f"Índice KM atualizado: {total} arquivos ativos, "
            f"{criados} novos, {atualizados} atualizados, {removidos} inativos."
        ),
        "quantidade_processada": total,
        "detalhes": {
            "base": str(KM_DOCUMENTOS_BASE),
            "arquivos_ativos": total,
            "criados": criados,
            "atualizados": atualizados,
            "inativos": removidos,
            "erros": erros,
            "por_extensao": por_extensao,
            "duracao_segundos": round(time.monotonic() - inicio, 3),
        },
    }


@login_required
def executar_indice_km(request):
    return _executar_automacao(
        request,
        executar_reindexacao_km_job,
        "Índice KM",
    )



_KM_INDEX_CACHE = None


def _km_limpar_cache():
    global _KM_INDEX_CACHE
    _KM_INDEX_CACHE = None


def _km_normalizar(valor):
    return "".join(ch for ch in str(valor or "").upper() if ch.isalnum())


def _km_eh_transmittal_letter(path):
    texto = str(path).replace("/", "\\").lower()
    nome = path.name.lower()
    return (
        "\\0 transmittal letters\\transmittal letters\\" in texto
        or "transmittal letters\\transmittal letters\\" in texto
        or nome.startswith("t-")
        or "transmittal" in nome
    )


def _km_indexar_documentos():
    """
    Indexa arquivos da árvore KM uma vez por processo do Django.

    Importante:
    - Mantém os Transmittal Letters no índice apenas como fallback.
    - Prioriza documentos técnicos em subpastas como 1.4 ETS.
    """
    global _KM_INDEX_CACHE

    if _KM_INDEX_CACHE is not None:
        return _KM_INDEX_CACHE

    itens = []

    if not KM_DOCUMENTOS_BASE.exists():
        _KM_INDEX_CACHE = itens
        return itens

    try:
        for arquivo in KM_DOCUMENTOS_BASE.rglob("*"):
            try:
                if not arquivo.is_file():
                    continue
            except OSError:
                continue

            nome_norm = _km_normalizar(arquivo.name)
            stem_norm = _km_normalizar(arquivo.stem)
            suffix = arquivo.suffix.lower()

            if not nome_norm:
                continue

            itens.append({
                "path": arquivo,
                "nome_norm": nome_norm,
                "stem_norm": stem_norm,
                "suffix": suffix,
                "is_transmittal_letter": _km_eh_transmittal_letter(arquivo),
            })
    except Exception:
        itens = []

    _KM_INDEX_CACHE = itens
    return itens


def _km_score_documento(documento, item):
    doc_norm = _km_normalizar(documento)

    if not doc_norm:
        return 0

    nome_norm = item["nome_norm"]
    stem_norm = item["stem_norm"]
    path = item["path"]
    suffix = item["suffix"]

    score = 0

    if stem_norm == doc_norm:
        score = 100
    elif nome_norm == doc_norm:
        score = 98
    elif doc_norm in stem_norm:
        score = 88
    elif doc_norm in nome_norm:
        score = 84
    elif stem_norm in doc_norm and len(stem_norm) >= 8:
        score = 60

    if not score:
        return 0

    # Prioriza documentos reais de engenharia sobre PDF do transmittal.
    score += KM_EXTENSOES_PRIORITARIAS.get(suffix, 5)

    if item["is_transmittal_letter"]:
        score -= 120
    else:
        score += 35

    # Subpastas técnicas costumam ter arquivos reais; raiz de letters tende a ser só carta.
    texto_path = str(path).replace("/", "\\").lower()
    if "\\0 transmittal letters\\" in texto_path and "\\transmittal letters\\" not in texto_path:
        score += 8

    # Nome típico do PDF de carta começa com T-; nunca deve vencer um docx/dwg real.
    if path.name.upper().startswith("T-"):
        score -= 80

    return score


def _km_score_documento_indexado(documento, item):
    doc_norm = _km_normalizar(documento)

    if not doc_norm:
        return 0

    nome_norm = item.nome_normalizado or _km_normalizar(item.nome_arquivo)
    stem_norm = item.stem_normalizado or _km_normalizar(Path(item.nome_arquivo).stem)
    suffix = (item.extensao or "").lower()

    score = 0

    if stem_norm == doc_norm:
        score = 100
    elif nome_norm == doc_norm:
        score = 98
    elif doc_norm in stem_norm:
        score = 88
    elif doc_norm in nome_norm:
        score = 84
    elif stem_norm in doc_norm and len(stem_norm) >= 8:
        score = 60

    documento_extraido_norm = _km_normalizar(item.documento_extraido)
    if documento_extraido_norm:
        if documento_extraido_norm == doc_norm:
            score = max(score, 105)
        elif doc_norm in documento_extraido_norm or documento_extraido_norm in doc_norm:
            score = max(score, 86)

    if not score:
        return 0

    score += KM_EXTENSOES_PRIORITARIAS.get(suffix, 5)

    if item.eh_transmittal_letter:
        score -= 120
    else:
        score += 35

    caminho_lower = (item.caminho_completo or "").replace("/", "\\").lower()
    if "\\0 transmittal letters\\" in caminho_lower and "\\transmittal letters\\" not in caminho_lower:
        score += 8

    if item.nome_arquivo.upper().startswith("T-"):
        score -= 80

    return score


def _km_buscar_documento_indexado(documento, permitir_transmittal=False):
    doc_norm = _km_normalizar(documento)

    if not doc_norm:
        return None

    qs = KMFileIndex.objects.filter(ativo=True)

    # Primeiro tenta reduzir no banco; se o código vier abreviado, ainda há fallback abaixo.
    candidatos_qs = qs.filter(
        Q(nome_normalizado__icontains=doc_norm)
        | Q(stem_normalizado__icontains=doc_norm)
        | Q(documento_extraido__icontains=str(documento or "").strip())
    )[:500]

    candidatos = []

    for item in candidatos_qs:
        score = _km_score_documento_indexado(documento, item)
        if score <= 0:
            continue

        if item.eh_transmittal_letter and not permitir_transmittal:
            continue

        candidatos.append((score, Path(item.caminho_completo)))

    if not candidatos:
        # Fallback amplo, ainda baseado no banco, para códigos extraídos/formatos inesperados.
        for item in qs.order_by("-indexado_em")[:2000]:
            score = _km_score_documento_indexado(documento, item)
            if score <= 0:
                continue

            if item.eh_transmittal_letter and not permitir_transmittal:
                continue

            candidatos.append((score, Path(item.caminho_completo)))

    if not candidatos and permitir_transmittal:
        for item in qs.filter(eh_transmittal_letter=True).order_by("-indexado_em")[:5000]:
            score = _km_score_documento_indexado(documento, item)
            if score > 0:
                candidatos.append((score, Path(item.caminho_completo)))

    if not candidatos:
        return None

    candidatos.sort(key=lambda par: (par[0], -len(str(par[1]))), reverse=True)
    return candidatos[0][1]


def _km_buscar_documento(documento, permitir_transmittal=False):
    """
    Busca o documento real no índice KM persistido.
    Se o índice ainda não existir, usa a varredura antiga como fallback.
    """
    arquivo = _km_buscar_documento_indexado(documento, permitir_transmittal=permitir_transmittal)
    if arquivo:
        return arquivo

    candidatos = []

    for item in _km_indexar_documentos():
        score = _km_score_documento(documento, item)

        if score <= 0:
            continue

        if item["is_transmittal_letter"] and not permitir_transmittal:
            continue

        candidatos.append((score, item["path"]))

    if not candidatos and permitir_transmittal:
        for item in _km_indexar_documentos():
            score = _km_score_documento(documento, item)
            if score > 0:
                candidatos.append((score, item["path"]))

    if not candidatos:
        return None

    candidatos.sort(key=lambda par: (par[0], -len(str(par[1]))), reverse=True)
    return candidatos[0][1]


def _km_resumo_filtros_ppt(request):
    filtros = []

    recebimentos = request.GET.getlist("recebimento")
    if recebimentos:
        filtros.append(f"Recebimento: {', '.join(recebimentos)}")

    tp = request.GET.getlist("tp")
    if tp:
        labels = []
        for item in tp:
            if item == "com_tp":
                labels.append("Com Nº Transpetro")
            elif item == "sem_tp":
                labels.append("Sem Nº Transpetro")
            else:
                labels.append(item)
        filtros.append(f"TP: {', '.join(labels)}")

    toc = request.GET.getlist("toc")
    if toc:
        filtros.append(f"TOCs selecionados: {len(toc)}")

    disciplinas = request.GET.getlist("disciplina")
    if disciplinas:
        filtros.append(f"Disciplinas: {len(disciplinas)}")

    phases = request.GET.getlist("phase")
    if phases:
        filtros.append(f"Phases: {len(phases)}")

    if not filtros:
        return "Sem filtros aplicados"

    return " • ".join(filtros)


def _ppt_truncate(texto, limite=42):
    texto = str(texto or "").strip()
    texto = texto.replace("¤", " → ")

    if len(texto) <= limite:
        return texto

    return texto[: limite - 3].rstrip() + "..."

def _km_buscar_documento_com_debug(documento):
    candidatos = []

    for item in _km_indexar_documentos():
        score = _km_score_documento(documento, item)
        if score > 0:
            candidatos.append((score, item["path"], item["is_transmittal_letter"]))

    candidatos.sort(key=lambda par: (par[0], -len(str(par[1]))), reverse=True)
    return candidatos



def _tr_texto(valor):
    return str(valor or "").strip()


def _tr_documento_normalizado(valor):
    """
    Normalização leve para exibição/busca textual.
    Mantém hífens porque muitos documentos KM/LD usam hífen como parte do código.
    """
    texto = _tr_texto(valor).upper()
    texto = texto.replace("\\", "/").split("/")[-1]
    texto = texto.split(".", 1)[0]
    texto = texto.replace("_", "-")
    texto = " ".join(texto.split())
    return texto.strip()


def _tr_documento_compacto(valor):
    """
    Normalização forte para comparação entre códigos vindos de fontes diferentes.

    Exemplos:
    - 108-505-02
    - 108_505_02
    - 108 505 02
    - DOC-108-505-02-REV0

    viram uma string comparável sem símbolos.
    """
    texto = _tr_documento_normalizado(valor)
    return "".join(ch for ch in texto if ch.isalnum())


def _tr_tokens_documento(valor):
    texto = _tr_documento_normalizado(valor)
    tokens = [t for t in re.split(r"[^A-Z0-9]+", texto) if t]
    return tokens


def _tr_score_match_documento(doc_busca, item_ld):
    """
    Pontua possíveis correspondências entre documento KM e registro LD.
    Evita depender apenas de iexact/icontains, porque os códigos KM podem vir
    resumidos e a LD pode conter prefixos/sufixos/revisões.
    """
    busca_norm = _tr_documento_normalizado(doc_busca)
    busca_compacta = _tr_documento_compacto(doc_busca)
    tokens = _tr_tokens_documento(doc_busca)

    campos = [
        getattr(item_ld, "documento", ""),
        getattr(item_ld, "titulo", ""),
        getattr(item_ld, "caminho_documento", ""),
        getattr(item_ld, "caminho_grd", ""),
        getattr(item_ld, "caminho_pcf", ""),
        getattr(item_ld, "caminho_resposta", ""),
        getattr(item_ld, "caminho_grd_resposta", ""),
    ]

    melhor = 0

    for valor in campos:
        texto = _tr_texto(valor)
        if not texto:
            continue

        texto_norm = _tr_documento_normalizado(texto)
        texto_compacto = _tr_documento_compacto(texto)

        if texto_norm == busca_norm:
            melhor = max(melhor, 100)

        if busca_norm and busca_norm in texto_norm:
            melhor = max(melhor, 85)

        if busca_compacta and busca_compacta == texto_compacto:
            melhor = max(melhor, 95)

        if busca_compacta and busca_compacta in texto_compacto:
            melhor = max(melhor, 80)

        if texto_compacto and texto_compacto in busca_compacta:
            melhor = max(melhor, 70)

        if tokens and all(token in texto_norm for token in tokens):
            melhor = max(melhor, 65)

        if tokens and all(token in texto_compacto for token in tokens):
            melhor = max(melhor, 60)

    return melhor


def _tr_buscar_ld_por_documento(numero_documento):
    """
    Localiza o documento KM dentro da Lista LD para permitir abertura direta
    do arquivo/pasta real na rede.

    A busca é propositalmente tolerante:
    - tenta match exato;
    - tenta contains no campo documento;
    - tenta comparar código compacto sem símbolos;
    - tenta procurar também em título e caminhos da LD.
    """
    doc = _tr_texto(numero_documento)

    if not doc:
        return None

    # 1) caminho rápido: exato no campo documento
    candidatos = DocumentoLD.objects.filter(documento__iexact=doc).order_by("-id")
    if candidatos.exists():
        return candidatos.first()

    doc_norm = _tr_documento_normalizado(doc)
    doc_compacto = _tr_documento_compacto(doc)

    if not doc_norm and not doc_compacto:
        return None

    # 2) contains tradicional
    candidatos = DocumentoLD.objects.filter(documento__icontains=doc_norm).order_by("-id")
    if candidatos.exists():
        return candidatos.first()

    # 3) busca em campos textuais/caminhos, útil quando a LD tem prefixos/sufixos
    busca_q = (
        Q(documento__icontains=doc_norm)
        | Q(titulo__icontains=doc_norm)
        | Q(caminho_documento__icontains=doc_norm)
        | Q(caminho_grd__icontains=doc_norm)
        | Q(caminho_pcf__icontains=doc_norm)
        | Q(caminho_resposta__icontains=doc_norm)
        | Q(caminho_grd_resposta__icontains=doc_norm)
    )
    candidatos_textuais = list(DocumentoLD.objects.filter(busca_q).order_by("-id")[:200])
    if candidatos_textuais:
        candidatos_textuais.sort(
            key=lambda item: _tr_score_match_documento(doc, item),
            reverse=True,
        )
        if _tr_score_match_documento(doc, candidatos_textuais[0]) >= 50:
            return candidatos_textuais[0]

    # 4) fallback amplo com pontuação. Limite para não pesar demais.
    melhor_item = None
    melhor_score = 0

    for item in DocumentoLD.objects.exclude(documento="").order_by("-id")[:2000]:
        score = _tr_score_match_documento(doc, item)
        if score > melhor_score:
            melhor_score = score
            melhor_item = item

        if melhor_score >= 95:
            break

    if melhor_item and melhor_score >= 60:
        return melhor_item

    return None


def _tr_caminho_documento_ld(item_ld):
    if not item_ld:
        return ""

    for campo in [
        "caminho_documento",
        "caminho_grd",
        "caminho_pcf",
        "caminho_resposta",
        "caminho_grd_resposta",
    ]:
        valor = getattr(item_ld, campo, "")
        if _tr_texto(valor):
            return valor

    return ""




def _km_buscar_documentos_em_lote(documentos, permitir_transmittal=False):
    """
    Resolve documentos KM em lote usando cache para evitar N+1 e scans repetidos.
    """
    resultados = {}

    docs_unicos = {
        _tr_texto(doc)
        for doc in documentos
        if _tr_texto(doc)
    }

    for documento in docs_unicos:
        cache_key = f"automacoes:km:doc:{_km_normalizar(documento)}"

        cached = cache.get(cache_key)
        if cached:
            resultados[documento] = Path(cached)
            continue

        arquivo = _km_buscar_documento(
            documento,
            permitir_transmittal=permitir_transmittal,
        )

        if arquivo:
            cache.set(
                cache_key,
                str(arquivo),
                _cache_ttl("CACHE_TTL_MEDIUM", 300),
            )

        resultados[documento] = arquivo

    return resultados


def _tr_montar_central_transmittals(registros):
    grupos = {}

    documentos_map = _km_buscar_documentos_em_lote(
        [item.documento for item in registros],
        permitir_transmittal=False,
    )

    for item in registros:
        numero = _tr_texto(item.transmittal_numero) or "Sem número"

        if numero not in grupos:
            grupos[numero] = {
                "numero": numero,
                "pdf_id": None,
                "pdf_path": "",
                "data_envio": "",
                "emissao": "",
                "proposito": "",
                "pastas": set(),
                "status": set(),
                "docs": [],
                "total_docs": 0,
            }

        grupo = grupos[numero]

        if item.arquivo_pdf and not grupo["pdf_id"]:
            grupo["pdf_id"] = item.id
            grupo["pdf_path"] = item.arquivo_pdf

        if item.data_envio and not grupo["data_envio"]:
            grupo["data_envio"] = item.data_envio

        if item.emissao and not grupo["emissao"]:
            grupo["emissao"] = item.emissao

        if item.proposito_emissao and not grupo["proposito"]:
            grupo["proposito"] = item.proposito_emissao

        if item.pasta:
            grupo["pastas"].add(item.pasta)

        if item.status_parse:
            grupo["status"].add(item.status_parse)

        item.km_arquivo = documentos_map.get(_tr_texto(item.documento))
        item.ld_vinculado = None

        grupo["docs"].append(item)

    transmittals = []

    for numero, grupo in grupos.items():
        grupo["docs"] = sorted(
            grupo["docs"],
            key=lambda doc: (
                _tr_texto(doc.pasta).lower(),
                _tr_texto(doc.documento).lower(),
                _tr_texto(doc.titulo).lower(),
            ),
        )
        grupo["total_docs"] = len(grupo["docs"])
        grupo["pastas_lista"] = sorted(grupo["pastas"])
        grupo["status_lista"] = sorted(grupo["status"])

        if any(str(s).upper() == "FALHA" for s in grupo["status_lista"]):
            grupo["status_badge"] = "FALHA"
            grupo["status_class"] = "bg-danger"
        elif any(str(s).upper() == "PARCIAL" for s in grupo["status_lista"]):
            grupo["status_badge"] = "PARCIAL"
            grupo["status_class"] = "bg-warning text-dark"
        elif grupo["status_lista"]:
            grupo["status_badge"] = "OK"
            grupo["status_class"] = "bg-success"
        else:
            grupo["status_badge"] = "—"
            grupo["status_class"] = "bg-secondary"

        transmittals.append(grupo)

    return sorted(
        transmittals,
        key=lambda grupo: (
            0 if grupo["numero"] != "Sem número" else 1,
            grupo["numero"].lower(),
        ),
    )


@login_required
def listar_transmittals_km(request):
    busca = request.GET.get("q", "").strip()
    pasta = request.GET.get("pasta", "").strip()
    emissao = request.GET.get("emissao", "").strip()
    transmittal = request.GET.get("transmittal", "").strip()

    registros = TransmittalKM.objects.all().order_by(
        "transmittal_numero",
        "pasta",
        "documento",
    )

    if busca:
        registros = registros.filter(
            Q(documento__icontains=busca)
            | Q(titulo__icontains=busca)
            | Q(transmittal_numero__icontains=busca)
            | Q(pasta__icontains=busca)
            | Q(emissao__icontains=busca)
            | Q(proposito_emissao__icontains=busca)
        )

    if pasta:
        registros = registros.filter(pasta__iexact=pasta)

    if emissao:
        registros = registros.filter(emissao__iexact=emissao)

    if transmittal:
        registros = registros.filter(transmittal_numero__iexact=transmittal)

    cache_key = (
        "automacoes:transmittals:list:"
        f"{busca}:{pasta}:{emissao}:{transmittal}"
    )

    cached_payload = cache.get(cache_key)

    if cached_payload:
        registros_lista = cached_payload["registros"]
        transmittals_agrupados = cached_payload["transmittals"]
    else:
        registros_lista = list(registros[:2000])
        transmittals_agrupados = _tr_montar_central_transmittals(registros_lista)

        cache.set(
            cache_key,
            {
                "registros": registros_lista,
                "transmittals": transmittals_agrupados,
            },
            _cache_ttl("CACHE_TTL_SHORT", 60),
        )

    total_documentos = len(registros_lista)
    total_transmittals = len(transmittals_agrupados)
    total_com_pdf = sum(1 for grupo in transmittals_agrupados if grupo.get("pdf_id"))
    total_sem_pdf = max(total_transmittals - total_com_pdf, 0)

    return render(
        request,
        "automacoes/transmittals_km.html",
        {
            "registros": registros_lista,
            "transmittals": transmittals_agrupados,
            "busca": busca,
            "pasta": pasta,
            "emissao": emissao,
            "transmittal": transmittal,
            "total_documentos": total_documentos,
            "total_transmittals": total_transmittals,
            "total_com_pdf": total_com_pdf,
            "total_sem_pdf": total_sem_pdf,
        },
    )


@login_required
def abrir_pdf_transmittal_km(request, pk):
    registro = TransmittalKM.objects.get(pk=pk)

    caminho_pdf = registro.arquivo_pdf

    if not caminho_pdf:
        raise Http404("PDF não localizado.")

    arquivo = Path(caminho_pdf)

    if not arquivo.exists():
        raise Http404(
            f"Arquivo não encontrado: {arquivo}"
        )

    return FileResponse(
        open(arquivo, "rb"),
        content_type="application/pdf",
    )


@login_required
def abrir_documento_transmittal_km(request, pk):
    registro = TransmittalKM.objects.get(pk=pk)

    arquivo = _km_buscar_documento(registro.documento, permitir_transmittal=False)

    # Fallback controlado: só abre o PDF do transmittal se nenhum documento técnico for localizado.
    if not arquivo and registro.arquivo_pdf:
        pdf = Path(registro.arquivo_pdf)
        if pdf.exists():
            arquivo = pdf

    if not arquivo:
        candidatos = _km_buscar_documento_com_debug(registro.documento)
        caminhos_testados = "\n".join(
            f"{score} | {'TRANS' if is_trans else 'DOC'} | {path}"
            for score, path, is_trans in candidatos[:20]
        )
        raise Http404(
            f"Documento KM não encontrado: {registro.documento}\n\n"
            f"Base KM: {KM_DOCUMENTOS_BASE}\n\n"
            f"Candidatos:\n{caminhos_testados}"
        )

    if os.name == "nt":
        os.startfile(str(arquivo))
        return HttpResponse(
            f"Arquivo aberto: {arquivo}",
            content_type="text/plain; charset=utf-8",
        )

    return FileResponse(
        open(arquivo, "rb"),
        as_attachment=False,
        filename=arquivo.name,
    )


@login_required
def abrir_pasta_documento_transmittal_km(request, pk):
    registro = TransmittalKM.objects.get(pk=pk)

    arquivo = _km_buscar_documento(registro.documento, permitir_transmittal=False)

    if not arquivo:
        candidatos = _km_buscar_documento_com_debug(registro.documento)
        caminhos_testados = "\n".join(
            f"{score} | {'TRANS' if is_trans else 'DOC'} | {path}"
            for score, path, is_trans in candidatos[:20]
        )
        raise Http404(
            f"Pasta KM não encontrada para: {registro.documento}\n\n"
            f"Base KM: {KM_DOCUMENTOS_BASE}\n\n"
            f"Candidatos:\n{caminhos_testados}"
        )

    pasta = arquivo.parent

    if os.name == "nt":
        os.startfile(str(pasta))
        return HttpResponse(
            f"Pasta aberta: {pasta}",
            content_type="text/plain; charset=utf-8",
        )

    return HttpResponse(
        f"Pasta localizada: {pasta}",
        content_type="text/plain; charset=utf-8",
    )




def _normalizar_revisao_pcf(valor):
    """
    Normaliza revisão PCF para comparação runtime.

    Exemplos:
    - "0" -> 0
    - "REV 1" -> 1
    - "R2" -> 2
    - "A" -> 1
    """
    valor = str(valor or "").strip().upper()

    if not valor:
        return -1

    valor = valor.replace("REV", "").replace("R", "").strip()

    try:
        return int(valor)
    except Exception:
        pass

    if len(valor) == 1 and valor.isalpha():
        return ord(valor) - 64

    return 0


def _obter_queryset_latest_pcfs(queryset):
    """
    Runtime only: mantém somente a maior revisão por documento.
    Não altera histórico e não cria migration.
    """
    latest_por_documento = {}

    for item in queryset:
        documento = (
            getattr(item, "numero_documento", None)
            or getattr(item, "documento", None)
            or ""
        ).strip()

        if not documento:
            continue

        revisao = _normalizar_revisao_pcf(
            getattr(item, "revisao_pcf", None)
            or getattr(item, "revisao", None)
        )

        atual = latest_por_documento.get(documento)

        if atual is None:
            latest_por_documento[documento] = item
            continue

        revisao_atual = _normalizar_revisao_pcf(
            getattr(atual, "revisao_pcf", None)
            or getattr(atual, "revisao", None)
        )

        # Em empate de revisão, mantém o registro mais novo/maior id.
        if revisao > revisao_atual or (
            revisao == revisao_atual and getattr(item, "id", 0) > getattr(atual, "id", 0)
        ):
            latest_por_documento[documento] = item

    ids = [obj.id for obj in latest_por_documento.values()]
    return queryset.filter(id__in=ids)



def _pcf_data_base(item):
    """
    Retorna a melhor data disponível para cálculo de aging PCF.

    Ordem de preferência:
    1. data_recebimento
    2. data_pcf / data_envio
    3. campos de criação/atualização como fallback operacional

    Não grava nada no banco. É normalização runtime.
    """
    from django.utils.dateparse import parse_date, parse_datetime

    campos_data = (
        "data_recebimento",
        "data_pcf",
        "data_envio",
        "recebido_em",
        "criado_em",
        "created_at",
        "atualizado_em",
        "updated_at",
    )

    for campo in campos_data:
        valor = getattr(item, campo, None)

        if not valor:
            continue

        if hasattr(valor, "date"):
            try:
                return valor.date()
            except Exception:
                pass

        if hasattr(valor, "year") and hasattr(valor, "month") and hasattr(valor, "day"):
            return valor

        if isinstance(valor, str):
            texto = valor.strip()
            if not texto:
                continue

            dt = parse_datetime(texto)
            if dt:
                return dt.date()

            data = parse_date(texto[:10])
            if data:
                return data

    return None


def _pcf_aging_dias(item):
    data_base = _pcf_data_base(item)
    if not data_base:
        return None
    try:
        return max((timezone.localdate() - data_base).days, 0)
    except Exception:
        return None


def _pcf_aging_bucket(dias):
    if dias is None:
        return "SEM DATA"
    if dias <= 7:
        return "0-7"
    if dias <= 15:
        return "8-15"
    if dias <= 30:
        return "16-30"
    return "30+"


def _pcf_criticidade_score(item):
    """
    Score operacional runtime de 0 a 100.

    Regras:
    - status é comparado de forma exata e case-insensitive;
    - RELEASED e RELEASED WITH COMMENTS são tratados separadamente;
    - volume de open comments pesa de forma progressiva;
    - aging/SLA aumenta o risco quando houver data válida;
    - registros sem data recebem pequeno acréscimo se ainda possuem pendência.
    """
    open_comments = int(getattr(item, "open_comments", 0) or 0)
    status = str(getattr(item, "status_final", "") or "").strip().upper()
    aging = _pcf_aging_dias(item)

    score = 0

    if status == "NOT RELEASED":
        score += 35
    elif status == "RELEASED WITH COMMENTS":
        score += 18
    elif status == "RELEASED":
        score += 0
    elif status:
        score += 10

    # Peso progressivo por volume de comentários abertos.
    score += min(round(open_comments * 0.7), 35)

    if aging is None:
        if open_comments > 0 and status != "RELEASED":
            score += 5
    elif aging > 45:
        score += 30
    elif aging > 30:
        score += 24
    elif aging > 15:
        score += 15
    elif aging > 7:
        score += 8

    if aging is not None and aging > 30 and open_comments > 0:
        score += 10

    if status == "RELEASED" and open_comments == 0:
        score = min(score, 5)

    return min(int(score), 100)


def _pcf_criticidade_classe(score):
    """
    Classe legada usada pelo dashboard.
    Mantida para não quebrar templates/testes existentes.
    """
    if score >= 70:
        return "CRÍTICO"
    if score >= 40:
        return "ATENÇÃO"
    return "OK"


def _pcf_criticidade_faixa(score):
    """
    Faixa executiva usada no PPT.
    """
    if score >= 80:
        return "CRITICAL"
    if score >= 60:
        return "HIGH"
    if score >= 40:
        return "MEDIUM"
    return "LOW"



def _pcf_enriquecer_runtime(registros):
    itens = []
    for item in registros:
        aging = _pcf_aging_dias(item)
        score = _pcf_criticidade_score(item)
        item.aging_dias_runtime = aging
        item.aging_bucket_runtime = _pcf_aging_bucket(aging)
        item.criticidade_score_runtime = score
        item.criticidade_classe_runtime = _pcf_criticidade_classe(score)
        item.criticidade_faixa_runtime = _pcf_criticidade_faixa(score)
        item.sla_vencido_runtime = bool(
            aging is not None
            and aging > 30
            and int(getattr(item, "open_comments", 0) or 0) > 0
        )
        itens.append(item)
    return itens


def _pcf_aging_summary(itens):
    buckets = {"0-7": 0, "8-15": 0, "16-30": 0, "30+": 0, "SEM DATA": 0}
    validos = []

    for item in itens:
        bucket = getattr(item, "aging_bucket_runtime", "SEM DATA")
        buckets[bucket] = buckets.get(bucket, 0) + 1
        aging = getattr(item, "aging_dias_runtime", None)
        if aging is not None:
            validos.append(aging)

    return {
        "aging_0_7": buckets.get("0-7", 0),
        "aging_8_15": buckets.get("8-15", 0),
        "aging_16_30": buckets.get("16-30", 0),
        "aging_30_plus": buckets.get("30+", 0),
        "aging_sem_data": buckets.get("SEM DATA", 0),
        "aging_medio": round(sum(validos) / len(validos), 1) if validos else 0,
    }


def _pcf_filtrar_aging_python(registros, aging):
    if not aging:
        return registros

    agings = aging if isinstance(aging, (list, tuple, set)) else [aging]
    agings = {str(item or "").strip() for item in agings if str(item or "").strip()}

    if not agings:
        return registros

    itens = _pcf_enriquecer_runtime(list(registros))
    ids = []

    for item in itens:
        bucket = getattr(item, "aging_bucket_runtime", "SEM DATA")
        if "sem_data" in agings and bucket == "SEM DATA":
            ids.append(item.id)
        elif bucket in agings:
            ids.append(item.id)

    return registros.filter(id__in=ids)


def _pcf_bool_param(request, nome):
    return str(request.GET.get(nome, "")).strip().lower() in {"1", "true", "on", "sim", "yes"}


def _pcf_query_params(request):
    busca = request.GET.get("q", "").strip()

    def _getlist(nome):
        valores = []
        for valor in request.GET.getlist(nome):
            valor = str(valor or "").strip()
            if valor:
                valores.append(valor)
        return valores

    tipos_selecionados = _getlist("tipo")
    status_selecionados = _getlist("status")
    agings_selecionados = _getlist("aging")
    faixas_comentarios_selecionadas = _getlist("faixa_comentarios")

    somente_open = _pcf_bool_param(request, "somente_open")
    somente_latest = _pcf_bool_param(request, "somente_latest")
    com_comentarios = _pcf_bool_param(request, "com_comentarios")

    return {
        "busca": busca,
        # Mantém chaves antigas para compatibilidade com templates/links já existentes.
        "tipo": tipos_selecionados[0] if len(tipos_selecionados) == 1 else "",
        "status": status_selecionados[0] if len(status_selecionados) == 1 else "",
        "aging": agings_selecionados[0] if len(agings_selecionados) == 1 else "",
        "faixa_comentarios": faixas_comentarios_selecionadas[0] if len(faixas_comentarios_selecionadas) == 1 else "",
        # Novas chaves enterprise multi-select.
        "tipos_selecionados": tipos_selecionados,
        "status_selecionados": status_selecionados,
        "agings_selecionados": agings_selecionados,
        "faixas_comentarios_selecionadas": faixas_comentarios_selecionadas,
        "somente_open": somente_open,
        "somente_latest": somente_latest,
        "com_comentarios": com_comentarios,
    }


def _filtrar_pcfs_timeline(request):
    """
    Filtro central de PCFs.
    Usado por Timeline, Dashboard e Export Excel para garantir
    que KPI, gráficos, lista e planilha usem exatamente a mesma base.
    """
    filtros = _pcf_query_params(request)

    registros = PCFTimeline.objects.all().order_by(
        "numero_documento",
        "revisao_pcf",
        "pcf_link",
    )

    busca = filtros["busca"]
    tipos_selecionados = filtros.get("tipos_selecionados", [])
    status_selecionados = filtros.get("status_selecionados", [])

    if busca:
        registros = registros.filter(
            Q(numero_documento__icontains=busca)
            | Q(numero_pcf__icontains=busca)
            | Q(pcf_link__icontains=busca)
            | Q(titulo__icontains=busca)
        )

    if tipos_selecionados:
        registros = registros.filter(tipo__in=tipos_selecionados)

    if status_selecionados:
        status_q = Q()
        status_normais = [s for s in status_selecionados if s != "__SEM_STATUS__"]

        if status_normais:
            status_q |= Q(status_final__in=status_normais)

        if "__SEM_STATUS__" in status_selecionados:
            status_q |= Q(status_final__isnull=True) | Q(status_final="")

        registros = registros.filter(status_q)

    if filtros["somente_open"]:
        registros = registros.filter(open_comments__gt=0)

    if filtros["com_comentarios"]:
        registros = registros.filter(qtd_comentarios__gt=0)

    faixas = filtros.get("faixas_comentarios_selecionadas", [])
    if faixas:
        faixa_q = Q()

        if "0" in faixas:
            faixa_q |= Q(open_comments=0)

        if "1-5" in faixas:
            faixa_q |= Q(open_comments__gte=1, open_comments__lte=5)

        if "6-10" in faixas:
            faixa_q |= Q(open_comments__gte=6, open_comments__lte=10)

        if "10+" in faixas:
            faixa_q |= Q(open_comments__gt=10)

        registros = registros.filter(faixa_q)


    if filtros["somente_latest"]:
        registros = _obter_queryset_latest_pcfs(registros)

    if filtros.get("agings_selecionados"):
        registros = _pcf_filtrar_aging_python(registros, filtros.get("agings_selecionados"))

    return registros


def _pcf_filtros_context(request):
    filtros = _pcf_query_params(request)

    tipos = (
        PCFTimeline.objects.exclude(tipo="")
        .values_list("tipo", flat=True)
        .distinct()
        .order_by("tipo")
    )

    status_disponiveis = (
        PCFTimeline.objects.exclude(status_final="")
        .exclude(status_final__isnull=True)
        .values_list("status_final", flat=True)
        .distinct()
        .order_by("status_final")
    )

    query_params = request.GET.copy()
    query_params.pop("page", None)

    return {
        **filtros,
        "tipos": tipos,
        "status_disponiveis": status_disponiveis,
        "querystring": query_params.urlencode(),
    }

@login_required
def listar_pcfs_timeline(request):
    registros = _filtrar_pcfs_timeline(request)
    filtros_context = _pcf_filtros_context(request)

    total = registros.count()
    total_open = registros.filter(open_comments__gt=0).count()
    total_sem_status = registros.filter(Q(status_final__isnull=True) | Q(status_final="")).count()
    total_comentarios = registros.aggregate(total=Sum("qtd_comentarios")).get("total") or 0
    total_comentarios_open = registros.aggregate(total=Sum("open_comments")).get("total") or 0

    registros_runtime = _pcf_enriquecer_runtime(list(registros))
    aging_summary = _pcf_aging_summary(registros_runtime)

    paginator = Paginator(registros_runtime, 50)
    page_obj = paginator.get_page(request.GET.get("page"))

    context = {
        **filtros_context,
        **aging_summary,
        "registros": page_obj,
        "page_obj": page_obj,
        "total": total,
        "total_open": total_open,
        "total_sem_status": total_sem_status,
        "total_comentarios": total_comentarios,
        "total_comentarios_open": total_comentarios_open,
    }

    return render(request, "automacoes/pcfs_timeline.html", context)



@login_required
def abrir_arquivo_pcf(request, pk):
    registro = PCFTimeline.objects.get(pk=pk)

    caminho = registro.caminho

    if not caminho:
        raise Http404("Arquivo PCF não localizado.")

    arquivo = Path(caminho)

    if not arquivo.exists():
        raise Http404(
            f"Arquivo não encontrado: {arquivo}"
        )

    return FileResponse(
        open(arquivo, "rb"),
        as_attachment=False,
        filename=arquivo.name,
    )


@login_required
def exportar_pcfs_timeline_excel(request):
    registros = _pcf_enriquecer_runtime(list(_filtrar_pcfs_timeline(request)))

    wb = Workbook()
    ws = wb.active
    ws.title = "Timeline PCFs"

    headers = [
        "Tipo",
        "PCF Link",
        "Nº PCF",
        "Nº Documento",
        "Título",
        "Revisão",
        "Data Recebimento",
        "Open Comments",
        "Qtd Comentários",
        "Status Final",
        "Caminho",
    ]

    ws.append(headers)

    header_fill = PatternFill("solid", fgColor="1F4E79")
    header_font = Font(color="FFFFFF", bold=True)

    for cell in ws[1]:
        cell.fill = header_fill
        cell.font = header_font

    for item in registros:
        ws.append([
            item.tipo,
            item.pcf_link,
            item.numero_pcf,
            item.numero_documento,
            item.titulo,
            item.revisao_pcf,
            item.data_recebimento,
            item.open_comments,
            item.qtd_comentarios,
            item.status_final,
            item.caminho,
        ])

    larguras = {
        "A": 25,
        "B": 35,
        "C": 30,
        "D": 30,
        "E": 60,
        "F": 12,
        "G": 18,
        "H": 16,
        "I": 18,
        "J": 25,
        "K": 90,
    }

    for col, width in larguras.items():
        ws.column_dimensions[col].width = width

    response = HttpResponse(
        content_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
    )
    response["Content-Disposition"] = 'attachment; filename="timeline_pcfs_filtrada.xlsx"'
    wb.save(response)
    return response



@login_required
def dashboard_pcfs(request):
    registros = _filtrar_pcfs_timeline(request)
    filtros_context = _pcf_filtros_context(request)

    total = registros.count()
    total_open = registros.filter(open_comments__gt=0).count()
    total_sem_status = registros.filter(Q(status_final__isnull=True) | Q(status_final="")).count()
    total_not_released = registros.filter(status_final__icontains="NOT RELEASED").count()
    total_released = registros.filter(status_final__icontains="RELEASED").exclude(status_final__icontains="NOT RELEASED").count()

    total_comentarios_abertos = registros.aggregate(total=Sum("open_comments")).get("total") or 0
    total_comentarios = registros.aggregate(total=Sum("qtd_comentarios")).get("total") or 0

    registros_runtime = _pcf_enriquecer_runtime(list(registros))
    aging_summary = _pcf_aging_summary(registros_runtime)

    total_sla_vencido = sum(1 for item in registros_runtime if getattr(item, "sla_vencido_runtime", False))
    total_criticidade_alta = sum(1 for item in registros_runtime if getattr(item, "criticidade_classe_runtime", "") == "CRÍTICO")
    sla_atendido = max(total_open - total_sla_vencido, 0)
    sla_atendido_percentual = round((sla_atendido / total_open) * 100, 1) if total_open else 100

    por_tipo = list(
        registros.values("tipo")
        .annotate(total=Count("id"), open_total=Sum("open_comments"))
        .order_by("-total", "tipo")
    )

    status_agregado = {}
    for status, total_status in registros.values_list("status_final").annotate(total=Count("id")):
        status_norm = normalizar_status(status)
        status_agregado[status_norm] = status_agregado.get(status_norm, 0) + (total_status or 0)

    por_status = [
        {"status_final": status, "total": total_status}
        for status, total_status in sorted(status_agregado.items(), key=lambda item: (-item[1], item[0]))[:10]
    ]

    top_pendencias = sorted(
        [item for item in registros_runtime if int(getattr(item, "open_comments", 0) or 0) > 0],
        key=lambda item: (
            getattr(item, "criticidade_score_runtime", 0),
            int(getattr(item, "open_comments", 0) or 0),
            getattr(item, "aging_dias_runtime", 0) or 0,
        ),
        reverse=True,
    )[:15]

    top_aging = sorted(
        [item for item in registros_runtime if int(getattr(item, "open_comments", 0) or 0) > 0],
        key=lambda item: (
            getattr(item, "aging_dias_runtime", -1) if getattr(item, "aging_dias_runtime", None) is not None else -1,
            int(getattr(item, "open_comments", 0) or 0),
        ),
        reverse=True,
    )[:15]

    recentes = registros.order_by("-atualizado_em")[:10]

    status_chart_labels = [item.get("status_final") or "SEM STATUS" for item in por_status]
    status_chart_values = [item.get("total") or 0 for item in por_status]
    tipo_chart_labels = [(item.get("tipo") or "Sem tipo") for item in por_tipo]
    tipo_chart_values = [item.get("total") or 0 for item in por_tipo]
    tipo_open_labels = [(item.get("tipo") or "Sem tipo") for item in por_tipo]
    tipo_open_values = [item.get("open_total") or 0 for item in por_tipo]
    aging_chart_labels = ["0-7", "8-15", "16-30", "30+", "Sem data"]
    aging_chart_values = [
        aging_summary.get("aging_0_7", 0),
        aging_summary.get("aging_8_15", 0),
        aging_summary.get("aging_16_30", 0),
        aging_summary.get("aging_30_plus", 0),
        aging_summary.get("aging_sem_data", 0),
    ]

    critical_rate = round((total_not_released / total) * 100, 1) if total else 0

    context = {
        **filtros_context,
        **aging_summary,
        "total": total,
        "total_open": total_open,
        "total_sem_status": total_sem_status,
        "total_not_released": total_not_released,
        "total_released": total_released,
        "total_comentarios": total_comentarios,
        "total_comentarios_abertos": total_comentarios_abertos,
        "critical_rate": critical_rate,
        "total_criticos": registros.filter(open_comments__gte=10).count(),
        "total_atencao": registros.filter(open_comments__gte=1, open_comments__lt=10).count(),
        "taxa_resolucao": round((total_released / total) * 100, 1) if total else 0,
        "total_sla_vencido": total_sla_vencido,
        "sla_atendido_percentual": sla_atendido_percentual,
        "total_criticidade_alta": total_criticidade_alta,
        "por_tipo": por_tipo,
        "por_status": por_status,
        "top_pendencias": top_pendencias,
        "top_aging": top_aging,
        "recentes": recentes,
        "status_chart_labels": status_chart_labels,
        "status_chart_values": status_chart_values,
        "tipo_chart_labels": tipo_chart_labels,
        "tipo_chart_values": tipo_chart_values,
        "tipo_open_labels": tipo_open_labels,
        "tipo_open_values": tipo_open_values,
        "aging_chart_labels": aging_chart_labels,
        "aging_chart_values": aging_chart_values,
    }

    return render(request, "automacoes/dashboard_pcfs.html", context)



def _ld_has_field(nome):
    return any(field.name == nome for field in DocumentoLD._meta.get_fields())


def _ld_texto(valor):
    return str(valor or "").strip()


def _ld_bool(valor):
    return _ld_texto(valor).lower() in {"1", "true", "on", "sim", "yes"}



def _ld_valores_distintos(campo, extras=None):
    valores = []
    vistos = set()

    if _ld_has_field(campo):
        for valor in (
            DocumentoLD.objects.exclude(**{campo: ""})
            .exclude(**{f"{campo}__isnull": True})
            .values_list(campo, flat=True)
            .distinct()
            .order_by(campo)
        ):
            texto = _ld_texto(valor)
            chave = texto.lower()
            if texto and chave not in vistos:
                vistos.add(chave)
                valores.append(texto)

    for valor in extras or []:
        texto = _ld_texto(valor)
        chave = texto.lower()
        if texto and chave not in vistos:
            vistos.add(chave)
            valores.append(texto)

    return valores


def _ld_normalizar_origem(valor):
    texto = _ld_texto(valor).lower()
    texto = " ".join(texto.replace("_", " ").replace("-", " ").split())

    if not texto:
        return ""

    if "marenova" in texto:
        return "ld marenova"

    if texto in {"ld", "lista ld", "aba ld"}:
        return "ld"

    return texto


def _ld_filtrar_origem(queryset, origem):
    """
    Filtra a origem sem zerar a lista quando a importação antiga veio com
    origem_aba vazia, "LD", "Lista LD" ou variações de escrita.

    Regra operacional:
    - LD Marenova: registros cuja origem contém "Marenova".
    - LD: registros LD explícitos + registros sem origem + registros que não são Marenova.
    - Outras origens: busca flexível por texto.
    """
    origem = _ld_texto(origem)

    if not origem or not _ld_has_field("origem_aba"):
        return queryset

    origem_norm = _ld_normalizar_origem(origem)

    if origem_norm == "ld marenova":
        return queryset.filter(origem_aba__icontains="Marenova")

    if origem_norm == "ld":
        return queryset.filter(
            Q(origem_aba__isnull=True)
            | Q(origem_aba="")
            | Q(origem_aba__iexact="LD")
            | Q(origem_aba__iexact="Lista LD")
            | Q(origem_aba__icontains="LD")
        ).exclude(origem_aba__icontains="Marenova")

    return queryset.filter(origem_aba__icontains=origem)


def _ld_revisao_peso(revisao):
    """
    Converte revisões LD para uma ordem comparável.

    Ordem esperada:
    vazio < 0 < 1 < 2 < A < B < C ...
    Também aceita formatos como "REV 0", "REV. A", "0.0".
    """
    texto = _ld_texto(revisao).upper()

    if not texto:
        return -1

    texto = (
        texto.replace("REVISÃO", "")
        .replace("REVISAO", "")
        .replace("REV.", "")
        .replace("REV", "")
        .replace("R.", "")
        .replace("R ", "")
        .strip()
    )

    texto_compacto = re.sub(r"[^A-Z0-9]", "", texto)

    if not texto_compacto:
        return -1

    if texto_compacto.isdigit():
        return int(texto_compacto)

    # Revisões alfabéticas devem vir depois das numéricas.
    letras = "".join(ch for ch in texto_compacto if "A" <= ch <= "Z")
    numeros = "".join(ch for ch in texto_compacto if ch.isdigit())

    peso_letras = 0
    for char in letras:
        peso_letras = peso_letras * 26 + (ord(char) - ord("A") + 1)

    peso_numeros = int(numeros) if numeros else 0

    return 1000 + (peso_letras * 100) + peso_numeros


def _ld_filtrar_ultimas_revisoes(queryset):
    """
    Mantém apenas a maior revisão de cada documento dentro do recorte já filtrado.

    Importante:
    - Não altera os smart-selects nem a querystring.
    - Respeita todos os filtros aplicados antes.
    - Usa o campo Documento como chave operacional.
    """
    dados = list(queryset.values_list("pk", "documento", "revisao"))

    ultimos = {}

    for pk, documento, revisao in dados:
        doc = _ld_texto(documento).upper()

        if not doc:
            doc = f"__PK__{pk}"

        peso = _ld_revisao_peso(revisao)

        if doc not in ultimos or peso > ultimos[doc][0]:
            ultimos[doc] = (peso, pk)

    ids = [pk for _, pk in ultimos.values()]

    return queryset.filter(pk__in=ids)


def _ld_getlist(request, nome):
    valores = []
    for valor in request.GET.getlist(nome):
        texto = _ld_texto(valor)
        if texto:
            valores.append(texto)

    if not valores:
        texto = _ld_texto(request.GET.get(nome))
        if texto:
            valores.append(texto)

    # Remove duplicados preservando ordem.
    unicos = []
    vistos = set()
    for valor in valores:
        chave = valor.casefold()
        if chave not in vistos:
            vistos.add(chave)
            unicos.append(valor)

    return unicos


def _ld_filtro_origens(queryset, origens):
    origens = [_ld_texto(item) for item in origens if _ld_texto(item)]

    if not origens or not _ld_has_field("origem_aba"):
        return queryset

    if len(origens) == 1:
        return _ld_filtrar_origem(queryset, origens[0])

    condicao = Q()

    for origem in origens:
        origem_norm = _ld_normalizar_origem(origem)

        if origem_norm == "ld marenova":
            condicao |= Q(origem_aba__icontains="Marenova")
        elif origem_norm == "ld":
            condicao |= (
                Q(origem_aba__isnull=True)
                | Q(origem_aba="")
                | Q(origem_aba__iexact="LD")
                | Q(origem_aba__iexact="Lista LD")
                | Q(origem_aba__icontains="LD")
            )
        else:
            condicao |= Q(origem_aba__icontains=origem)

    return queryset.filter(condicao)


def _ld_filtrar_por_tipos_documentais(queryset, tipos_doc):
    tipos_doc = {_ld_texto(tipo).upper() for tipo in tipos_doc if _ld_texto(tipo)}

    if not tipos_doc:
        return queryset

    ids_tipo_doc = [
        pk
        for pk, documento in queryset.values_list("pk", "documento")
        if extrair_tipo_documental(documento) in tipos_doc
    ]

    return queryset.filter(pk__in=ids_tipo_doc)


def _ld_filtrar_queryset(request):
    busca = _ld_texto(request.GET.get("q"))

    origens = _ld_getlist(request, "origem")
    disciplinas = _ld_getlist(request, "disciplina")
    tipos_doc = [item.upper() for item in _ld_getlist(request, "tipo_doc")]
    status_docs = _ld_getlist(request, "status_doc")
    status_grds = _ld_getlist(request, "status_grd")
    status_pcfs = _ld_getlist(request, "status_pcf")

    com_pcf = _ld_bool(request.GET.get("com_pcf"))
    sem_pcf = _ld_bool(request.GET.get("sem_pcf"))
    com_resposta = _ld_bool(request.GET.get("com_resposta"))
    ultimas_revisoes = _ld_bool(request.GET.get("ultimas_revisoes"))

    filtro_rapido = _ld_texto(request.GET.get("filtro"))

    if filtro_rapido == "recebidos":
        status_docs = ["Recebido"]
    elif filtro_rapido == "aprovados":
        status_docs = ["Aprovado"]
    elif filtro_rapido == "grd_emitido":
        status_grds = ["Emitido"]
    elif filtro_rapido == "com_pcf":
        com_pcf = True
        sem_pcf = False
    elif filtro_rapido == "sem_pcf":
        sem_pcf = True
        com_pcf = False
    elif filtro_rapido == "com_resposta":
        com_resposta = True
    elif filtro_rapido == "not_released":
        status_pcfs = ["NOT RELEASED"]
    elif filtro_rapido == "ultimas_revisoes":
        ultimas_revisoes = True

    registros = DocumentoLD.objects.all().order_by("documento", "revisao")

    registros = _ld_filtro_origens(registros, origens)

    if busca:
        registros = registros.filter(
            Q(documento__icontains=busca)
            | Q(titulo__icontains=busca)
            | Q(disciplina__icontains=busca)
            | Q(grd__icontains=busca)
            | Q(pcf__icontains=busca)
            | Q(pcf_resposta__icontains=busca)
            | Q(grd_resposta__icontains=busca)
        )

    registros = _ld_filtrar_por_tipos_documentais(registros, tipos_doc)

    if disciplinas:
        registros = registros.filter(disciplina__in=disciplinas)

    if status_docs:
        registros = registros.filter(status_documento__in=status_docs)

    if status_grds:
        registros = registros.filter(status_grd__in=status_grds)

    if status_pcfs:
        condicao_status_pcf = Q()
        for status_pcf in status_pcfs:
            status_pcf_norm = status_pcf.strip().upper()
            if status_pcf_norm in ["RELEASED", "NOT RELEASED"]:
                condicao_status_pcf |= Q(status_final_pcf__iexact=status_pcf)
            else:
                condicao_status_pcf |= Q(status_final_pcf__icontains=status_pcf)

        registros = registros.filter(condicao_status_pcf)

    if com_pcf and not sem_pcf:
        registros = registros.exclude(pcf__isnull=True).exclude(pcf="")

    if sem_pcf and not com_pcf:
        registros = registros.filter(Q(pcf__isnull=True) | Q(pcf=""))

    if com_resposta:
        registros = registros.exclude(pcf_resposta__isnull=True).exclude(pcf_resposta="")

    if ultimas_revisoes:
        registros = _ld_filtrar_ultimas_revisoes(registros)

    filtros = {
        "busca": busca,
        "origem": origens[0] if len(origens) == 1 else "",
        "disciplina": disciplinas[0] if len(disciplinas) == 1 else "",
        "tipo_doc": tipos_doc[0] if len(tipos_doc) == 1 else "",
        "status_doc": status_docs[0] if len(status_docs) == 1 else "",
        "status_grd": status_grds[0] if len(status_grds) == 1 else "",
        "status_pcf": status_pcfs[0] if len(status_pcfs) == 1 else "",
        "origens_selecionadas": origens,
        "disciplinas_selecionadas": disciplinas,
        "tipos_doc_selecionados": tipos_doc,
        "status_docs_selecionados": status_docs,
        "status_grds_selecionados": status_grds,
        "status_pcfs_selecionados": status_pcfs,
        "com_pcf": com_pcf,
        "sem_pcf": sem_pcf,
        "com_resposta": com_resposta,
        "ultimas_revisoes": ultimas_revisoes,
        "filtro_rapido": filtro_rapido,
    }

    return registros, filtros


def _ld_kpis(registros):
    total = registros.count()

    return {
        "total": total,
        "total_exclusivos": registros.order_by().values("documento").distinct().count(),
        "total_recebidos": registros.filter(status_documento__iexact="Recebido").count(),
        "total_aprovados": registros.filter(status_documento__iexact="Aprovado").count(),
        "total_emitidos": registros.filter(status_grd__iexact="Emitido").count(),
        "total_com_pcf": registros.exclude(pcf__isnull=True).exclude(pcf="").count(),
        "total_sem_pcf": registros.filter(Q(pcf__isnull=True) | Q(pcf="")).count(),
        "total_com_resposta": registros.exclude(pcf_resposta__isnull=True).exclude(pcf_resposta="").count(),
    }


def _ld_resolver_caminho(caminho_salvo):
    return resolver_caminho_ld(caminho_salvo)


def _ld_hyperlink(caminho):
    return gerar_hyperlink_ld(caminho)




def _ld_querystring(request, updates=None, clears=None):
    """
    Monta querystring preservando os filtros atuais, removendo paginação
    e evitando parâmetros duplicados.

    Usado pelos chips rápidos da Lista LD.
    """
    query = request.GET.copy()
    query.pop("page", None)

    for key in clears or []:
        query.pop(key, None)

    for key, value in (updates or {}).items():
        query.pop(key, None)
        if value not in (None, "", False):
            query[key] = str(value)

    encoded = query.urlencode()
    return f"?{encoded}" if encoded else ""


def _ld_chip(label, query, active=False):
    return {
        "label": label,
        "query": query,
        "active": active,
    }


def _ld_montar_chips(request, filtros, status_documentos, status_grds):
    status_doc = _ld_texto(filtros.get("status_doc"))
    status_grd = _ld_texto(filtros.get("status_grd"))
    status_pcf = _ld_texto(filtros.get("status_pcf"))

    com_pcf = bool(filtros.get("com_pcf"))
    sem_pcf = bool(filtros.get("sem_pcf"))
    com_resposta = bool(filtros.get("com_resposta"))
    ultimas_revisoes = bool(filtros.get("ultimas_revisoes"))

    status_documento_chips = [
        _ld_chip(
            "Todos",
            _ld_querystring(
                request,
                clears=["status_doc", "filtro"],
            ),
            active=not status_doc,
        )
    ]

    for valor in status_documentos:
        status_documento_chips.append(
            _ld_chip(
                valor,
                _ld_querystring(
                    request,
                    updates={"status_doc": valor},
                    clears=["status_doc", "filtro"],
                ),
                active=status_doc.casefold() == _ld_texto(valor).casefold(),
            )
        )

    status_grd_chips = [
        _ld_chip(
            "Todos",
            _ld_querystring(
                request,
                clears=["status_grd", "filtro"],
            ),
            active=not status_grd,
        )
    ]

    for valor in status_grds:
        status_grd_chips.append(
            _ld_chip(
                valor,
                _ld_querystring(
                    request,
                    updates={"status_grd": valor},
                    clears=["status_grd", "filtro"],
                ),
                active=status_grd.casefold() == _ld_texto(valor).casefold(),
            )
        )

    operacional_chips = [
        _ld_chip(
            "Todos",
            "",
            active=not any(
                key != "page" and _ld_texto(value)
                for key, value in request.GET.items()
            ),
        ),
        _ld_chip(
            "Recebidos",
            _ld_querystring(
                request,
                updates={"status_doc": "Recebido"},
                clears=["status_doc", "filtro"],
            ),
            active=status_doc.casefold() == "recebido",
        ),
        _ld_chip(
            "Aprovados",
            _ld_querystring(
                request,
                updates={"status_doc": "Aprovado"},
                clears=["status_doc", "filtro"],
            ),
            active=status_doc.casefold() == "aprovado",
        ),
        _ld_chip(
            "GRD emitido",
            _ld_querystring(
                request,
                updates={"status_grd": "Emitido"},
                clears=["status_grd", "filtro"],
            ),
            active=status_grd.casefold() == "emitido",
        ),
        _ld_chip(
            "Com PCF",
            _ld_querystring(
                request,
                updates={"com_pcf": "1"},
                clears=["sem_pcf", "filtro"],
            ),
            active=com_pcf and not sem_pcf,
        ),
        _ld_chip(
            "Sem PCF",
            _ld_querystring(
                request,
                updates={"sem_pcf": "1"},
                clears=["com_pcf", "filtro"],
            ),
            active=sem_pcf and not com_pcf,
        ),
        _ld_chip(
            "Com resposta",
            _ld_querystring(
                request,
                updates={"com_resposta": "1"},
                clears=["filtro"],
            ),
            active=com_resposta,
        ),
        _ld_chip(
            "Not Released",
            _ld_querystring(
                request,
                updates={"status_pcf": "NOT RELEASED"},
                clears=["status_pcf", "filtro"],
            ),
            active=status_pcf.casefold() == "not released",
        ),
        _ld_chip(
            "Últimas revisões",
            _ld_querystring(
                request,
                updates={"ultimas_revisoes": "1"},
                clears=["filtro"],
            ),
            active=ultimas_revisoes,
        ),
    ]

    return {
        "status_documento_chips": status_documento_chips,
        "status_grd_chips": status_grd_chips,
        "operacional_chips": operacional_chips,
    }


@login_required
def listar_ld(request):
    registros, filtros = _ld_filtrar_queryset(request)

    tipos_encontrados = {
        extrair_tipo_documental(documento)
        for documento in DocumentoLD.objects.values_list("documento", flat=True)
    }
    tipos_documentais = sorted(tipo for tipo in tipos_encontrados if tipo)

    kpis = _ld_kpis(registros)

    disciplinas = _ld_valores_distintos("disciplina")
    origens = _ld_valores_distintos("origem_aba", extras=["LD", "LD Marenova"])

    # Mantém as duas origens operacionais sempre disponíveis, mesmo quando a
    # importação antiga gravou origem_aba em branco.
    origens_norm = []
    for origem_item in ["LD", "LD Marenova", *origens]:
        if origem_item not in origens_norm:
            origens_norm.append(origem_item)
    origens = origens_norm

    status_documentos = _ld_valores_distintos("status_documento")
    status_grds = _ld_valores_distintos("status_grd")
    status_pcfs = _ld_valores_distintos("status_final_pcf", extras=["RELEASED", "NOT RELEASED"])

    chips_ld = _ld_montar_chips(
        request,
        filtros,
        status_documentos,
        status_grds,
    )

    paginator = Paginator(registros, 25)
    page_number = request.GET.get("page")
    page_obj = paginator.get_page(page_number)

    query_params = request.GET.copy()
    query_params.pop("page", None)
    query_params.pop("export", None)
    query_string = query_params.urlencode()

    filtros_ativos = []

    if filtros["busca"]:
        filtros_ativos.append({"label": "Busca", "valor": filtros["busca"]})

    for label, valores in [
        ("Origem", filtros["origens_selecionadas"]),
        ("Tipo", filtros["tipos_doc_selecionados"]),
        ("Disciplina", filtros["disciplinas_selecionadas"]),
        ("Status documento", filtros["status_docs_selecionados"]),
        ("Status GRD", filtros["status_grds_selecionados"]),
        ("Status PCF", filtros["status_pcfs_selecionados"]),
    ]:
        for valor in valores:
            filtros_ativos.append({"label": label, "valor": valor})

    if filtros["com_pcf"]:
        filtros_ativos.append({"label": "Filtro", "valor": "Com PCF"})
    if filtros["sem_pcf"]:
        filtros_ativos.append({"label": "Filtro", "valor": "Sem PCF"})
    if filtros["com_resposta"]:
        filtros_ativos.append({"label": "Filtro", "valor": "Com resposta"})
    if filtros["ultimas_revisoes"]:
        filtros_ativos.append({"label": "Filtro", "valor": "Últimas revisões"})

    return render(
        request,
        "automacoes/lista_ld.html",
        {
            "registros": page_obj,
            "page_obj": page_obj,
            "query_string": query_string,
            "querystring": query_string,
            "filtros_ativos": filtros_ativos,
            "tipos_documentais": tipos_documentais,

            "origens": origens,
            "disciplinas": disciplinas,
            "status_documentos": status_documentos,
            "status_grds": status_grds,
            "status_pcfs": status_pcfs,

            **chips_ld,
            **filtros,
            **kpis,
        },
    )



@login_required
def exportar_ld_excel(request):
    registros, _ = _ld_filtrar_queryset(request)

    wb = Workbook()
    ws = wb.active
    ws.title = "Lista LD Filtrada"

    headers = [
        "Origem",
        "Documento",
        "Revisão",
        "Disciplina",
        "Título",
        "Status Documento",
        "Status GRD",
        "Status PCF",
        "GRD",
        "Data GRD",
        "PCF",
        "Data PCF",
        "Resposta PCF",
        "Data Resposta",
        "GRD Resposta",
        "Caminho Documento",
        "Caminho GRD",
        "Caminho PCF",
        "Caminho Resposta",
        "Caminho GRD Resposta",
    ]

    ws.append(headers)

    header_fill = PatternFill("solid", fgColor="1F4E79")
    header_font = Font(color="FFFFFF", bold=True)

    for cell in ws[1]:
        cell.fill = header_fill
        cell.font = header_font

    for item in registros:
        row = [
            getattr(item, "origem_aba", ""),
            item.documento,
            item.revisao,
            item.disciplina,
            item.titulo,
            item.status_documento,
            item.status_grd,
            item.status_final_pcf,
            item.grd,
            item.data_grd,
            item.pcf,
            item.data_pcf,
            item.pcf_resposta,
            item.data_resposta,
            item.grd_resposta,
            item.caminho_documento,
            item.caminho_grd,
            item.caminho_pcf,
            item.caminho_resposta,
            item.caminho_grd_resposta,
        ]

        ws.append(row)

        current_row = ws.max_row

        caminho_cols = {
            16: item.caminho_documento,
            17: item.caminho_grd,
            18: item.caminho_pcf,
            19: item.caminho_resposta,
            20: item.caminho_grd_resposta,
        }

        for col_idx, caminho in caminho_cols.items():
            if caminho:
                cell = ws.cell(row=current_row, column=col_idx)
                cell.hyperlink = _ld_hyperlink(caminho)
                cell.style = "Hyperlink"

    widths = {
        "A": 16,
        "B": 34,
        "C": 10,
        "D": 28,
        "E": 60,
        "F": 20,
        "G": 18,
        "H": 20,
        "I": 18,
        "J": 14,
        "K": 36,
        "L": 14,
        "M": 36,
        "N": 14,
        "O": 18,
        "P": 80,
        "Q": 80,
        "R": 80,
        "S": 80,
        "T": 80,
    }

    for col, width in widths.items():
        ws.column_dimensions[col].width = width

    response = HttpResponse(
        content_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
    )
    response["Content-Disposition"] = 'attachment; filename="lista_ld_filtrada.xlsx"'
    wb.save(response)

    return response



def _ld_chart_items(queryset, campo, limite=10):
    dados = list(
        queryset.values(campo)
        .annotate(total=Count("id"))
        .order_by("-total")[:limite]
    )

    maior = max([item.get("total") or 0 for item in dados] or [1])

    return [
        {
            "label": item.get(campo) or "Sem informação",
            "total": item.get("total") or 0,
            "pct": round(((item.get("total") or 0) / maior) * 100, 1) if maior else 0,
        }
        for item in dados
    ]


def _ld_binary_chart(label_ok, total_ok, label_gap, total_gap):
    maior = max(total_ok, total_gap, 1)
    return [
        {"label": label_ok, "total": total_ok, "pct": round((total_ok / maior) * 100, 1)},
        {"label": label_gap, "total": total_gap, "pct": round((total_gap / maior) * 100, 1)},
    ]


def _ld_exportar_dashboard_ppt(request):
    from io import BytesIO

    from pptx import Presentation
    from pptx.dml.color import RGBColor
    from pptx.util import Inches, Pt

    registros, filtros = _ld_filtrar_queryset(request)
    kpis = _ld_kpis(registros)

    total = kpis["total"] or 0
    total_sem_resposta = registros.filter(
        Q(pcf_resposta__isnull=True) | Q(pcf_resposta="")
    ).exclude(Q(pcf__isnull=True) | Q(pcf="")).count()

    total_not_released = registros.filter(status_final_pcf__iexact="NOT RELEASED").count()

    taxa_pcf = round((kpis["total_com_pcf"] / total) * 100, 1) if total else 0
    taxa_grd = round((kpis["total_emitidos"] / total) * 100, 1) if total else 0
    taxa_aprovacao = round((kpis["total_aprovados"] / total) * 100, 1) if total else 0
    saude = round((taxa_pcf + taxa_grd + taxa_aprovacao) / 3, 1) if total else 0

    disciplina_chart = _ld_chart_items(registros, "disciplina", 7)
    status_doc_chart = _ld_chart_items(registros, "status_documento", 7)
    status_grd_chart = _ld_chart_items(registros, "status_grd", 7)

    prs = Presentation()
    prs.slide_width = Inches(13.333)
    prs.slide_height = Inches(7.5)

    bg = RGBColor(8, 13, 28)
    cyan = RGBColor(56, 189, 248)
    white = RGBColor(248, 250, 252)
    muted = RGBColor(148, 163, 184)
    green = RGBColor(34, 197, 94)
    orange = RGBColor(251, 191, 36)

    def add_text(slide, text, x, y, w, h, size=22, bold=False, color=white):
        box = slide.shapes.add_textbox(Inches(x), Inches(y), Inches(w), Inches(h))
        tf = box.text_frame
        tf.clear()
        p = tf.paragraphs[0]
        run = p.add_run()
        run.text = str(text)
        run.font.size = Pt(size)
        run.font.bold = bold
        run.font.color.rgb = color
        return box

    def add_card(slide, title, value, subtitle, x, y, w=2.1, h=1.0, accent=cyan):
        shape = slide.shapes.add_shape(1, Inches(x), Inches(y), Inches(w), Inches(h))
        shape.fill.solid()
        shape.fill.fore_color.rgb = RGBColor(15, 23, 42)
        shape.line.color.rgb = RGBColor(51, 65, 85)
        add_text(slide, title.upper(), x + .12, y + .10, w - .24, .22, 8, True, cyan)
        add_text(slide, value, x + .12, y + .34, w - .24, .34, 21, True, white)
        add_text(slide, subtitle, x + .12, y + .72, w - .24, .20, 8, False, muted)
        bar = slide.shapes.add_shape(1, Inches(x), Inches(y + h - .05), Inches(w), Inches(.04))
        bar.fill.solid()
        bar.fill.fore_color.rgb = accent
        bar.line.fill.background()

    def add_bars(slide, title, items, x, y, w, h):
        add_text(slide, title, x, y, w, .28, 15, True, white)
        add_text(slide, "Top registros no filtro atual", x, y + .32, w, .20, 8, False, muted)
        top_y = y + .70
        max_total = max([item["total"] for item in items] or [1])
        for idx, item in enumerate(items[:7]):
            yy = top_y + idx * .42
            add_text(slide, item["label"][:34], x, yy, w * .55, .20, 9, False, white)
            track = slide.shapes.add_shape(1, Inches(x + w * .55), Inches(yy + .04), Inches(w * .30), Inches(.09))
            track.fill.solid()
            track.fill.fore_color.rgb = RGBColor(30, 41, 59)
            track.line.fill.background()
            fill_w = (w * .30) * ((item["total"] or 0) / max_total) if max_total else 0
            fill = slide.shapes.add_shape(1, Inches(x + w * .55), Inches(yy + .04), Inches(fill_w), Inches(.09))
            fill.fill.solid()
            fill.fill.fore_color.rgb = cyan
            fill.line.fill.background()
            add_text(slide, item["total"], x + w * .88, yy - .02, w * .12, .20, 10, True, white)

    # Slide 1
    slide = prs.slides.add_slide(prs.slide_layouts[6])
    slide.background.fill.solid()
    slide.background.fill.fore_color.rgb = bg
    add_text(slide, "Dashboard Executivo LD", .45, .35, 8.6, .45, 28, True, white)
    add_text(slide, "Lista de Documentos • GRD • PCF • Revisões • Status documental", .45, .86, 8.8, .30, 12, False, cyan)
    add_card(slide, "Total linhas", total, "resultado atual", .45, 1.45)
    add_card(slide, "Únicos", kpis["total_exclusivos"], "documentos únicos", 2.75, 1.45)
    add_card(slide, "Recebidos", kpis["total_recebidos"], f"{taxa_aprovacao}% aprov.", 5.05, 1.45, accent=green)
    add_card(slide, "GRD emitido", kpis["total_emitidos"], f"{taxa_grd}% cobertura", 7.35, 1.45, accent=orange)
    add_card(slide, "Com PCF", kpis["total_com_pcf"], f"{taxa_pcf}% cobertura", 9.65, 1.45, accent=cyan)
    add_card(slide, "Saúde", f"{saude}%", "score operacional", 11.95, 1.45, w=1.0)
    add_bars(slide, "Distribuição por Disciplina", disciplina_chart, .55, 2.85, 5.8, 3.8)
    add_bars(slide, "Status Documento", status_doc_chart, 6.9, 2.85, 5.7, 3.8)
    add_text(slide, "GED_PROFISSIONAL • LD Intelligence", .45, 7.05, 7.0, .20, 8, False, muted)

    # Slide 2
    slide = prs.slides.add_slide(prs.slide_layouts[6])
    slide.background.fill.solid()
    slide.background.fill.fore_color.rgb = bg
    add_text(slide, "Cobertura documental LD", .45, .35, 8.8, .45, 26, True, white)
    add_card(slide, "Com PCF", kpis["total_com_pcf"], f"{taxa_pcf}% da base", .45, 1.15)
    add_card(slide, "Sem PCF", kpis["total_sem_pcf"], "gaps operacionais", 2.75, 1.15, accent=orange)
    add_card(slide, "Com resposta", kpis["total_com_resposta"], "respostas PCF", 5.05, 1.15, accent=green)
    add_card(slide, "Sem resposta", total_sem_resposta, "PCFs sem retorno", 7.35, 1.15, accent=orange)
    add_card(slide, "Not Released", total_not_released, "status crítico PCF", 9.65, 1.15, accent=RGBColor(248, 113, 113))
    add_bars(slide, "Status GRD", status_grd_chart, .55, 2.65, 5.8, 3.9)
    add_bars(slide, "Pendências por disciplina", _ld_chart_items(registros.filter(Q(pcf__isnull=True) | Q(pcf="")), "disciplina", 7), 6.9, 2.65, 5.7, 3.9)

    output = BytesIO()
    prs.save(output)
    output.seek(0)

    response = HttpResponse(
        output.getvalue(),
        content_type="application/vnd.openxmlformats-officedocument.presentationml.presentation",
    )
    response["Content-Disposition"] = 'attachment; filename="dashboard_ld_executivo.pptx"'
    return response


@login_required
def dashboard_ld(request):
    if request.GET.get("export") == "pptx":
        return _ld_exportar_dashboard_ppt(request)

    registros, filtros = _ld_filtrar_queryset(request)

    kpis = _ld_kpis(registros)

    total_not_released = registros.filter(
        status_final_pcf__iexact="NOT RELEASED"
    ).count()

    total_released = registros.filter(
        status_final_pcf__iexact="RELEASED"
    ).count()

    total_sem_status_doc = registros.filter(
        Q(status_documento__isnull=True) | Q(status_documento="")
    ).count()

    total_sem_grd = registros.filter(
        Q(status_grd__isnull=True) | Q(status_grd="")
    ).count()

    total_sem_resposta = registros.filter(
        Q(pcf_resposta__isnull=True) | Q(pcf_resposta="")
    ).exclude(
        Q(pcf__isnull=True) | Q(pcf="")
    ).count()

    taxa_pcf = round((kpis["total_com_pcf"] / kpis["total"]) * 100, 1) if kpis["total"] else 0
    taxa_grd = round((kpis["total_emitidos"] / kpis["total"]) * 100, 1) if kpis["total"] else 0
    taxa_aprovacao = round((kpis["total_aprovados"] / kpis["total"]) * 100, 1) if kpis["total"] else 0
    taxa_recebimento = round((kpis["total_recebidos"] / kpis["total"]) * 100, 1) if kpis["total"] else 0
    saude_operacional = round((taxa_pcf + taxa_grd + taxa_recebimento) / 3, 1) if kpis["total"] else 0

    disciplina_chart = _ld_chart_items(registros, "disciplina", 10)
    origem_chart = _ld_chart_items(registros, "origem_aba", 8)
    status_doc_chart = _ld_chart_items(registros, "status_documento", 8)
    status_grd_chart = _ld_chart_items(registros, "status_grd", 8)
    pcf_chart = _ld_binary_chart("Com PCF", kpis["total_com_pcf"], "Sem PCF", kpis["total_sem_pcf"])
    resposta_chart = _ld_binary_chart("Com resposta", kpis["total_com_resposta"], "Sem resposta", total_sem_resposta)

    top_disciplinas_pendentes = list(
        registros.filter(Q(pcf__isnull=True) | Q(pcf=""))
        .values("disciplina")
        .annotate(total=Count("id"))
        .order_by("-total")[:10]
    )

    top_not_released = registros.filter(
        status_final_pcf__iexact="NOT RELEASED"
    ).order_by("documento", "revisao")[:12]

    recentes = registros.order_by("-id")[:12]

    disciplinas = _ld_valores_distintos("disciplina")
    origens = _ld_valores_distintos("origem_aba", extras=["LD", "LD Marenova"])
    origens_norm = []
    for origem_item in ["LD", "LD Marenova", *origens]:
        if origem_item not in origens_norm:
            origens_norm.append(origem_item)
    origens = origens_norm

    status_documentos = _ld_valores_distintos("status_documento")
    status_grds = _ld_valores_distintos("status_grd")
    status_pcfs = _ld_valores_distintos("status_final_pcf", extras=["RELEASED", "NOT RELEASED"])
    tipos_encontrados = {
        extrair_tipo_documental(documento)
        for documento in DocumentoLD.objects.values_list("documento", flat=True)
    }
    tipos_documentais = sorted(tipo for tipo in tipos_encontrados if tipo)

    query_params = request.GET.copy()
    query_params.pop("page", None)
    query_params.pop("export", None)
    querystring = query_params.urlencode()

    filtros_ativos = []

    if filtros["busca"]:
        filtros_ativos.append({"label": "Busca", "valor": filtros["busca"]})

    for label, valores in [
        ("Origem", filtros["origens_selecionadas"]),
        ("Tipo", filtros["tipos_doc_selecionados"]),
        ("Disciplina", filtros["disciplinas_selecionadas"]),
        ("Status documento", filtros["status_docs_selecionados"]),
        ("Status GRD", filtros["status_grds_selecionados"]),
        ("Status PCF", filtros["status_pcfs_selecionados"]),
    ]:
        for valor in valores:
            filtros_ativos.append({"label": label, "valor": valor})

    if filtros["com_pcf"]:
        filtros_ativos.append({"label": "Filtro", "valor": "Com PCF"})
    if filtros["sem_pcf"]:
        filtros_ativos.append({"label": "Filtro", "valor": "Sem PCF"})
    if filtros["com_resposta"]:
        filtros_ativos.append({"label": "Filtro", "valor": "Com resposta"})
    if filtros["ultimas_revisoes"]:
        filtros_ativos.append({"label": "Filtro", "valor": "Últimas revisões"})

    return render(
        request,
        "automacoes/dashboard_ld.html",
        {
            **kpis,
            **filtros,
            "querystring": querystring,
            "query_string": querystring,
            "filtros_ativos": filtros_ativos,

            "tipos_documentais": tipos_documentais,
            "origens": origens,
            "disciplinas": disciplinas,
            "status_documentos": status_documentos,
            "status_grds": status_grds,
            "status_pcfs": status_pcfs,

            "total_not_released": total_not_released,
            "total_released": total_released,
            "total_sem_status_doc": total_sem_status_doc,
            "total_sem_grd": total_sem_grd,
            "total_sem_resposta": total_sem_resposta,
            "taxa_pcf": taxa_pcf,
            "taxa_grd": taxa_grd,
            "taxa_aprovacao": taxa_aprovacao,
            "taxa_recebimento": taxa_recebimento,
            "saude_operacional": saude_operacional,

            "disciplina_chart": disciplina_chart,
            "origem_chart": origem_chart,
            "status_doc_chart": status_doc_chart,
            "status_grd_chart": status_grd_chart,
            "pcf_chart": pcf_chart,
            "resposta_chart": resposta_chart,
            "top_disciplinas_pendentes": top_disciplinas_pendentes,
            "top_not_released": top_not_released,
            "recentes": recentes,
        },
    )


@login_required
def dashboard_transmittals(request):
    registros = TransmittalKM.objects.all()

    total_registros = registros.count()
    total_transmittals = registros.values("transmittal_numero").distinct().count()
    total_ok = registros.filter(status_parse__icontains="OK").count()
    total_pdf = registros.exclude(arquivo_pdf="").count()
    total_sem_pdf = registros.filter(Q(arquivo_pdf__isnull=True) | Q(arquivo_pdf="")).count()

    media_docs_transmittal = round(total_registros / total_transmittals, 1) if total_transmittals else 0

    por_pasta = list(
        registros.values("pasta")
        .annotate(total=Count("id"))
        .order_by("-total")[:10]
    )

    por_emissao = list(
        registros.values("emissao")
        .annotate(total=Count("id"))
        .order_by("-total")[:10]
    )

    top_transmittals = list(
        registros.values("transmittal_numero")
        .annotate(total=Count("id"))
        .order_by("-total")[:10]
    )

    ultimos = registros.order_by("-criado_em")[:15]

    pastas_labels = [item.get("pasta") or "Sem pasta" for item in por_pasta]
    pastas_values = [item.get("total") or 0 for item in por_pasta]

    emissoes_labels = [item.get("emissao") or "Sem emissão" for item in por_emissao]
    emissoes_values = [item.get("total") or 0 for item in por_emissao]

    transmittal_labels = [item.get("transmittal_numero") or "Sem número" for item in top_transmittals]
    transmittal_values = [item.get("total") or 0 for item in top_transmittals]

    return render(
        request,
        "automacoes/dashboard_transmittals.html",
        {
            "total_registros": total_registros,
            "total_transmittals": total_transmittals,
            "total_ok": total_ok,
            "total_pdf": total_pdf,
            "total_sem_pdf": total_sem_pdf,
            "media_docs_transmittal": media_docs_transmittal,
            "por_pasta": por_pasta,
            "por_emissao": por_emissao,
            "top_transmittals": top_transmittals,
            "ultimos": ultimos,
            "pastas_labels": pastas_labels,
            "pastas_values": pastas_values,
            "emissoes_labels": emissoes_labels,
            "emissoes_values": emissoes_values,
            "transmittal_labels": transmittal_labels,
            "transmittal_values": transmittal_values,
        },
    )



@login_required
def abrir_arquivo_ld(request, pk, tipo):
    registro = DocumentoLD.objects.get(pk=pk)

    mapa = {
        "documento": registro.caminho_documento,
        "grd": registro.caminho_grd,
        "pcf": registro.caminho_pcf,
        "resposta": registro.caminho_resposta,
        "grd-resposta": registro.caminho_grd_resposta,
    }

    caminho_salvo = mapa.get(tipo)

    if not caminho_salvo:
        raise Http404("Caminho não localizado para este item da LD.")

    arquivo, candidatos = _ld_resolver_caminho(caminho_salvo)

    if not arquivo:
        html = "<h3>Arquivo ou pasta não encontrado.</h3>"
        html += f"<p><strong>Caminho salvo no banco:</strong> {_ld_texto(caminho_salvo)}</p>"
        html += "<p><strong>Caminhos testados:</strong></p><ul>"

        for candidato in candidatos:
            html += f"<li>{candidato}</li>"

        html += "</ul>"
        html += "<p>Verifique se a pasta da rede está acessível e se o caminho salvo continua válido.</p>"

        return HttpResponse(html, status=404)

    try:
        if arquivo.is_dir():
            os.startfile(str(arquivo))
            html = "<h3>Pasta aberta no Windows Explorer.</h3>"
            html += f"<p><strong>Caminho:</strong> {arquivo}</p>"
            html += "<p>Você pode fechar esta aba.</p>"
            return HttpResponse(html)

        return FileResponse(
            open(arquivo, "rb"),
            as_attachment=False,
            filename=arquivo.name,
        )

    except Exception as exc:
        html = "<h3>Arquivo ou pasta localizado, mas não foi possível abrir automaticamente.</h3>"
        html += f"<p><strong>Caminho:</strong> {arquivo}</p>"
        html += f"<p><strong>Erro:</strong> {exc}</p>"
        return HttpResponse(html, status=500)


# ============================================================
# BUSCA GLOBAL GED ENTERPRISE
# ============================================================

def _bg_texto(valor):
    return str(valor or "").strip()


def _bg_url(path):
    return path


def _bg_score(q, *valores):
    q_norm = _km_normalizar(q)
    if not q_norm:
        return 0

    melhor = 0
    for valor in valores:
        texto = _bg_texto(valor)
        if not texto:
            continue

        texto_norm = _km_normalizar(texto)

        if texto_norm == q_norm:
            melhor = max(melhor, 100)
        elif q_norm in texto_norm:
            melhor = max(melhor, 85)
        elif texto_norm in q_norm and len(texto_norm) >= 6:
            melhor = max(melhor, 70)
        elif q.lower() in texto.lower():
            melhor = max(melhor, 60)

    return melhor


def _bg_limite(qs, limite=20):
    return list(qs[:limite])


@login_required
def abrir_km_index(request, pk):
    item = KMFileIndex.objects.get(pk=pk, ativo=True)
    arquivo = Path(item.caminho_completo)

    if not arquivo.exists():
        raise Http404(f"Arquivo KM não encontrado: {arquivo}")

    if os.name == "nt":
        os.startfile(str(arquivo))
        return HttpResponse(
            f"Arquivo aberto: {arquivo}",
            content_type="text/plain; charset=utf-8",
        )

    return FileResponse(
        open(arquivo, "rb"),
        as_attachment=False,
        filename=arquivo.name,
    )


@login_required
def abrir_pasta_km_index(request, pk):
    item = KMFileIndex.objects.get(pk=pk, ativo=True)
    arquivo = Path(item.caminho_completo)
    pasta = arquivo.parent if arquivo.suffix else arquivo

    if not pasta.exists():
        raise Http404(f"Pasta KM não encontrada: {pasta}")

    if os.name == "nt":
        os.startfile(str(pasta))
        return HttpResponse(
            f"Pasta aberta: {pasta}",
            content_type="text/plain; charset=utf-8",
        )

    return HttpResponse(
        f"Pasta localizada: {pasta}",
        content_type="text/plain; charset=utf-8",
    )




@login_required
def dashboard_search(request):
    dias = request.GET.get("dias", 30)
    contexto = obter_search_analytics(dias=dias)

    return render(
        request,
        "automacoes/dashboard_search.html",
        contexto,
    )

@login_required
def busca_global_ged(request):
    q = (request.GET.get("q") or request.GET.get("busca") or "").strip()
    tipo = (request.GET.get("tipo") or "todos").strip().lower()

    contexto = buscar_global_enterprise(
        q,
        tipo=tipo,
        usuario=request.user,
        origem="web",
        auditar=bool(q),
    )

    return render(
        request,
        "automacoes/busca_global.html",
        contexto,
    )


@login_required
def api_busca_global_ged(request):
    q = _bg_texto(request.GET.get("q") or request.GET.get("busca"))
    if len(q) < 2:
        return JsonResponse({"results": []})

    q_norm = _km_normalizar(q)
    results = []

    for item in KMFileIndex.objects.filter(ativo=True).filter(
        Q(nome_arquivo__icontains=q)
        | Q(documento_extraido__icontains=q)
        | Q(nome_normalizado__icontains=q_norm)
        | Q(stem_normalizado__icontains=q_norm)
    ).order_by("eh_transmittal_letter", "nome_arquivo")[:8]:
        results.append({
            "type": "KM",
            "title": item.nome_arquivo,
            "subtitle": item.documento_extraido or item.pasta,
            "url": f"/automacoes/km-index/{item.id}/abrir/",
        })

    for item in DocumentoLD.objects.filter(
        Q(documento__icontains=q) | Q(titulo__icontains=q)
    ).order_by("documento")[:5]:
        results.append({
            "type": "LD",
            "title": item.documento,
            "subtitle": item.titulo[:120] if item.titulo else "",
            "url": f"/automacoes/ld/?q={q}",
        })

    for item in TransmittalKM.objects.filter(
        Q(documento__icontains=q)
        | Q(titulo__icontains=q)
        | Q(transmittal_numero__icontains=q)
    ).order_by("transmittal_numero")[:5]:
        results.append({
            "type": "Transmittal",
            "title": item.documento or item.transmittal_numero,
            "subtitle": item.titulo[:120] if item.titulo else item.transmittal_numero,
            "url": f"/automacoes/transmittals-km/?q={q}",
        })

    return JsonResponse({"results": results[:15]})





@login_required
def busca_global(request):
    """
    Legacy global search route compatibility.

    Keeps /automacoes/busca-global/ alive and delegates to the current
    enterprise search implementation when a query is provided.
    """
    termo = request.GET.get("q", "").strip()
    resultados = []
    analytics = {}

    if termo:
        try:
            resultados = buscar_global_enterprise(termo)
        except TypeError:
            resultados = buscar_global_enterprise(request)
        except Exception:
            resultados = []

        try:
            analytics = obter_search_analytics()
        except Exception:
            analytics = {}

    return render(
        request,
        "automacoes/busca_global.html",
        {
            "q": termo,
            "termo": termo,
            "resultados": resultados,
            "analytics": analytics,
        },
    )


# ============================================================
# UNIFIED OPERATIONS CENTER
# ============================================================

@login_required
def ops_center(request):
    context = {
        "ops": OperationsCenterService.build_dashboard(),
    }

    return render(
        request,
        "automacoes/ops_center.html",
        context,
    )


@login_required
def ops_center_runtime_partial(request):
    context = {
        "ops": OperationsCenterService.build_dashboard(),
    }

    return render(
        request,
        "automacoes/partials/_ops_runtime_observability.html",
        context,
    )


@login_required
def ops_center_events_partial(request):
    return render(
        request,
        "automacoes/partials/_ops_runtime_events.html",
        {
            "runtime_events": RuntimeEventStreamService.build_stream(limit=20),
            "runtime_events_summary": RuntimeEventStreamService.summary(),
        },
    )


@login_required
def ops_center_live_partial(request):
    from apps.automacoes.services.live_operations import (
        LiveOperationsService,
    )

    return render(
        request,
        "automacoes/partials/_ops_live_operations.html",
        LiveOperationsService.build_payload(),
    )

@login_required
def runtime_health_api(request):
    return JsonResponse(RuntimeHealthAPIService.health())


@login_required
def runtime_metrics_api(request):
    return JsonResponse(RuntimeHealthAPIService.metrics())


@login_required
def runtime_events_api(request):
    return JsonResponse(RuntimeHealthAPIService.events())


@login_required
def runtime_retention_dry_run_api(request):
    days = request.GET.get("days") or 90

    result = RuntimeRetentionService.cleanup_all(
        days=int(days),
        dry_run=True,
    )

    return JsonResponse(result)


@login_required
def importar_lista_km(request):
    """
    Importa a LD mestre Kongsberg para DocumentoKM e executa o cruzamento
    inicial com TransmittalKM e DocumentoLD.
    """
    if request.method == "POST":
        arquivo = (
            request.FILES.get("arquivo")
            or request.FILES.get("file")
            or request.FILES.get("planilha")
            or request.FILES.get("xlsx")
        )

        if not arquivo:
            messages.error(request, "Selecione a planilha .xlsx da LD Kongsberg.")
            return redirect("automacoes:importar_lista_km")

        try:
            resultado = importar_ld_kongsberg(
                arquivo,
                nome_arquivo=getattr(arquivo, "name", "LD Kongsberg"),
                executar_cruzamento=True,
            )

            if resultado.get("ok"):
                messages.success(request, resultado.get("mensagem", "LD Kongsberg importada."))
            else:
                messages.warning(
                    request,
                    f"{resultado.get('mensagem', 'Importação concluída com alertas.')} "
                    f"Erros: {resultado.get('total_erros', 0)}"
                )

            return redirect("automacoes:dashboard_km_ld")

        except Exception as exc:
            messages.error(request, f"Erro ao importar LD Kongsberg: {exc}")
            return redirect("automacoes:importar_lista_km")

    return render(
        request,
        "automacoes/importar_lista_km.html",
        {},
    )


@login_required
def executar_sync_km_ld(request):
    """
    Reexecuta o cruzamento DocumentoKM ↔ TransmittalKM ↔ DocumentoLD
    sem reimportar a planilha.
    """
    try:
        resultado = executar_cruzamento_ld_km()
        if resultado.get("ok"):
            messages.success(request, resultado.get("mensagem", "Sync KM ↔ LD executado."))
        else:
            messages.warning(request, resultado.get("mensagem", "Sync KM ↔ LD concluído com alertas."))
    except Exception as exc:
        messages.error(request, f"Erro ao executar sync KM ↔ LD: {exc}")

    return redirect("automacoes:dashboard_km_ld")


@login_required


def _km_clean_getlist(request, nome):
    valores = []
    for valor in request.GET.getlist(nome):
        valor = str(valor or "").strip()
        if valor:
            valores.append(valor)
    legado = str(request.GET.get(nome, "") or "").strip()
    if legado and legado not in valores:
        valores.append(legado)
    return valores


def _km_recebido_q():
    return (
        (
            ~Q(transmittal_numero="")
            & Q(transmittal_numero__isnull=False)
        )
        | (
            ~Q(data_recebimento_km="")
            & Q(data_recebimento_km__isnull=False)
        )
    )


def _km_distinct_values(campo):
    if not _model_has_field(DocumentoKM, campo):
        return []
    return list(
        DocumentoKM.objects.exclude(**{campo: ""})
        .exclude(**{f"{campo}__isnull": True})
        .values_list(campo, flat=True)
        .distinct()
        .order_by(campo)
    )


def _km_filter_state(request):
    return {
        "busca": request.GET.get("q", "").strip(),
        "phases": _km_clean_getlist(request, "phase"),
        "tocs": _km_clean_getlist(request, "toc"),
        "disciplinas": _km_clean_getlist(request, "disciplina"),
        "transmittals": _km_clean_getlist(request, "transmittal"),
        "recebimentos": _km_clean_getlist(request, "recebimento"),
        "tps": _km_clean_getlist(request, "tp"),
    }


def _km_apply_filters(registros, filtros):
    busca = filtros.get("busca", "")
    phases = filtros.get("phases", [])
    tocs = filtros.get("tocs", [])
    disciplinas = filtros.get("disciplinas", [])
    transmittals = filtros.get("transmittals", [])
    recebimentos = filtros.get("recebimentos", [])
    tps = filtros.get("tps", [])

    if busca:
        registros = registros.filter(
            Q(numero_km__icontains=busca)
            | Q(titulo__icontains=busca)
            | Q(disciplina__icontains=busca)
            | Q(status_km__icontains=busca)
            | Q(transmittal_numero__icontains=busca)
            | Q(documento_tp__icontains=busca)
            | Q(phase__icontains=busca)
            | Q(toc__icontains=busca)
            | Q(released_for__icontains=busca)
        )

    if phases and _model_has_field(DocumentoKM, "phase"):
        registros = registros.filter(phase__in=phases)

    if tocs and _model_has_field(DocumentoKM, "toc"):
        registros = registros.filter(toc__in=tocs)

    if disciplinas and _model_has_field(DocumentoKM, "disciplina"):
        registros = registros.filter(disciplina__in=disciplinas)

    if transmittals and _model_has_field(DocumentoKM, "transmittal_numero"):
        registros = registros.filter(transmittal_numero__in=transmittals)

    recebido_q = _km_recebido_q()

    if recebimentos:
        if "recebido" in recebimentos and "nao_recebido" not in recebimentos:
            registros = registros.filter(recebido_q)
        elif "nao_recebido" in recebimentos and "recebido" not in recebimentos:
            registros = registros.exclude(recebido_q)

    if tps:
        if "com_tp" in tps and "sem_tp" not in tps:
            registros = registros.exclude(documento_tp="").exclude(documento_tp__isnull=True)
        elif "sem_tp" in tps and "com_tp" not in tps:
            registros = registros.filter(Q(documento_tp="") | Q(documento_tp__isnull=True))

    return registros


def _km_pct(valor, total):
    return round((valor / total) * 100, 1) if total else 0




def _km_ld_base_unica_sem_marenova():
    """
    Base LD executiva para o PPT KM.

    Regra oficial:
    - considerar somente registros da origem "LD";
    - não considerar "LD Marenova";
    - contar somente documentos únicos não vazios.

    A Lista LD exibe esse mesmo conceito como "Documentos únicos"
    quando o filtro Origem = LD está aplicado.
    """
    qs = DocumentoLD.objects.all()

    if _model_has_field(DocumentoLD, "origem_aba"):
        qs = qs.filter(origem_aba__iexact="LD")
    else:
        marenova_q = Q()
        for campo in (
            "documento",
            "titulo",
            "disciplina",
            "contratada",
            "fornecedor",
            "origem",
            "empresa",
        ):
            if _model_has_field(DocumentoLD, campo):
                marenova_q |= Q(**{f"{campo}__icontains": "marenova"})

        if marenova_q:
            qs = qs.exclude(marenova_q)

    if not _model_has_field(DocumentoLD, "documento"):
        return qs.count()

    return (
        qs.exclude(documento="")
        .exclude(documento__isnull=True)
        .order_by()
        .values("documento")
        .distinct()
        .count()
    )


def _km_bar_chart(qs, campo, limite=8):
    if not _model_has_field(DocumentoKM, campo):
        return []

    dados = list(
        qs.exclude(**{campo: ""})
        .exclude(**{f"{campo}__isnull": True})
        .values(campo)
        .annotate(total=Count("id"))
        .order_by("-total", campo)[:limite]
    )
    maior = max([item["total"] for item in dados], default=0)

    return [
        {
            "label": item.get(campo) or "—",
            "total": item.get("total") or 0,
            "pct": _km_pct(item.get("total") or 0, maior),
        }
        for item in dados
    ]


def _km_simple_chart(itens):
    total = sum(valor for _, valor in itens)
    return [
        {
            "label": label,
            "total": valor,
            "pct": _km_pct(valor, total),
        }
        for label, valor in itens
    ]


def _km_active_filter_chips(filtros):
    chips = []
    if filtros.get("busca"):
        chips.append({"label": "Busca", "valor": filtros["busca"]})

    mapa = [
        ("Phase", "phases"),
        ("TOC", "tocs"),
        ("Discipline", "disciplinas"),
        ("Transmittal", "transmittals"),
        ("Recebimento", "recebimentos"),
        ("Documento TP", "tps"),
    ]

    rotulos = {
        "recebido": "Recebidos",
        "nao_recebido": "Não recebidos",
        "com_tp": "Com N° Transpetro",
        "sem_tp": "Sem Nº Transpetro",
    }

    for label, chave in mapa:
        valores = filtros.get(chave) or []
        if valores:
            texto = ", ".join(rotulos.get(v, v) for v in valores[:4])
            if len(valores) > 4:
                texto += f" +{len(valores) - 4}"
            chips.append({"label": label, "valor": texto})

    return chips


def _km_exportar_excel_filtrado(registros):
    wb = Workbook()
    ws = wb.active
    ws.title = "Lista KM filtrada"

    headers = [
        "Number",
        "Title",
        "Discipline",
        "TOC",
        "Phase",
        "Status KM",
        "Transmittal Number",
        "Data Recebimento KM",
        "Documento TP",
        "Released For",
        "Responsible",
    ]
    ws.append(headers)

    for cell in ws[1]:
        cell.font = Font(bold=True)
        cell.fill = PatternFill("solid", fgColor="D9EAF7")

    for item in registros:
        ws.append([
            getattr(item, "numero_km", "") or "",
            getattr(item, "titulo", "") or "",
            getattr(item, "disciplina", "") or "",
            getattr(item, "toc", "") or "",
            getattr(item, "phase", "") or "",
            getattr(item, "status_km", "") or "",
            getattr(item, "transmittal_numero", "") or "",
            getattr(item, "data_recebimento_km", "") or "",
            getattr(item, "documento_tp", "") or "",
            getattr(item, "released_for", "") or "",
            getattr(item, "responsible", "") or "",
        ])

    for column_cells in ws.columns:
        max_len = max(len(str(cell.value or "")) for cell in column_cells)
        ws.column_dimensions[column_cells[0].column_letter].width = min(max(max_len + 2, 12), 55)

    response = HttpResponse(
        content_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
    )
    response["Content-Disposition"] = 'attachment; filename="lista_km_filtrada.xlsx"'
    wb.save(response)
    return response




def _km_exportar_dashboard_ppt(request):
    from io import BytesIO

    from django.http import HttpResponse
    from pptx import Presentation
    from pptx.dml.color import RGBColor
    from pptx.enum.shapes import MSO_SHAPE
    from pptx.util import Inches, Pt

    filtros = _km_filter_state(request)
    registros_base = DocumentoKM.objects.all()
    registros = _km_apply_filters(registros_base.order_by("numero_km"), filtros)

    recebido_q = _km_recebido_q()

    total = registros.count()
    total_km = registros_base.count()
    total_ld = _km_ld_base_unica_sem_marenova()
    recebidos = registros.filter(recebido_q).count()
    com_tp = registros.exclude(documento_tp="").exclude(documento_tp__isnull=True).count()

    # Regra operacional KM:
    # pendência executiva é o recebido ainda sem Nº Transpetro.
    pendentes = max(recebidos - com_tp, 0)
    sem_tp = pendentes

    # Vínculo LD executivo:
    # percentual de documentos com Nº Transpetro sobre a base LD única válida
    # sem considerar Marenova.
    km_com_ld = com_tp
    km_sem_ld = max(total_ld - km_com_ld, 0)

    cobertura_recebimento = _km_pct(recebidos, total)
    cobertura_tp = _km_pct(com_tp, recebidos)
    cobertura_vinculo = _km_pct(km_com_ld, total_ld)

    saude_operacional = round(
        (cobertura_recebimento * 0.20)
        + (cobertura_tp * 0.40)
        + (cobertura_vinculo * 0.40),
        1,
    ) if total else 0

    disciplina_chart = _km_bar_chart(registros, "disciplina", 8)
    phase_chart = _km_bar_chart(registros, "phase", 8)
    toc_chart = _km_bar_chart(registros, "toc", 8)
    status_km_chart = _km_bar_chart(registros, "status_km", 8)

    recebimento_chart = _km_simple_chart([
        ("Recebidos", recebidos),
        ("Pendentes", pendentes),
    ])
    tp_chart = _km_simple_chart([
        ("Com N° Transpetro", com_tp),
        ("Sem Nº Transpetro", sem_tp),
    ])
    vinculo_chart = _km_simple_chart([
        ("Com Nº Transpetro", km_com_ld),
        ("Base LD única", total_ld),
    ])

    matriz_recebimento_tp = [
        {
            "label": "Recebidos com TP",
            "total": registros.filter(recebido_q)
            .exclude(documento_tp="")
            .exclude(documento_tp__isnull=True)
            .count(),
        },
        {
            "label": "Recebidos sem TP",
            "total": registros.filter(recebido_q)
            .filter(Q(documento_tp="") | Q(documento_tp__isnull=True))
            .count(),
        },
        {
            "label": "Pendentes com TP",
            "total": registros.exclude(recebido_q)
            .exclude(documento_tp="")
            .exclude(documento_tp__isnull=True)
            .count(),
        },
        {
            "label": "Pendentes sem TP",
            "total": registros.exclude(recebido_q)
            .filter(Q(documento_tp="") | Q(documento_tp__isnull=True))
            .count(),
        },
    ]

    query_params = request.GET.copy()
    query_params.pop("page", None)
    query_params.pop("export", None)
    filtros_ativos = _km_resumo_filtros_ppt(request)

    prs = Presentation()
    prs.slide_width = Inches(13.333)
    prs.slide_height = Inches(7.5)

    bg = RGBColor(8, 13, 28)
    panel = RGBColor(15, 23, 42)
    panel_2 = RGBColor(17, 34, 64)
    border = RGBColor(51, 65, 85)
    cyan = RGBColor(56, 189, 248)
    blue = RGBColor(59, 130, 246)
    white = RGBColor(248, 250, 252)
    muted = RGBColor(148, 163, 184)
    green = RGBColor(34, 197, 94)
    orange = RGBColor(251, 191, 36)
    red = RGBColor(248, 113, 113)

    def clean_text(value, limit=None):
        texto = str(value or "—")
        texto = texto.replace("¤", " → ").replace("\xa4", " → ")
        texto = " ".join(texto.split())
        if limit and len(texto) > limit:
            return texto[: max(limit - 1, 1)].rstrip() + "…"
        return texto

    def add_text(slide, text, x, y, w, h, size=18, bold=False, color=white):
        box = slide.shapes.add_textbox(Inches(x), Inches(y), Inches(w), Inches(h))
        tf = box.text_frame
        tf.clear()
        tf.word_wrap = True
        p = tf.paragraphs[0]
        run = p.add_run()
        run.text = clean_text(text)
        run.font.size = Pt(size)
        run.font.bold = bold
        run.font.color.rgb = color
        return box

    def add_slide(title, subtitle=None):
        slide = prs.slides.add_slide(prs.slide_layouts[6])
        slide.background.fill.solid()
        slide.background.fill.fore_color.rgb = bg

        add_text(slide, title, .55, .32, 8.8, .42, 25, True, white)
        if subtitle:
            add_text(slide, subtitle, .58, .78, 8.8, .28, 9, False, muted)

        logo_paths = [
            Path(settings.BASE_DIR) / "static" / "documentos" / "logo_dorange.png",
            Path(settings.BASE_DIR) / "staticfiles" / "documentos" / "logo_dorange.png",
        ]
        for logo_path in logo_paths:
            if logo_path.exists():
                try:
                    slide.shapes.add_picture(str(logo_path), Inches(11.25), Inches(.30), height=Inches(.45))
                except Exception:
                    pass
                break

        add_text(slide, "GED PROFISSIONAL • KM", 10.15, .84, 2.6, .22, 8, False, muted)
        return slide

    def add_card(slide, title, value, subtitle, x, y, w=2.35, h=1.05, accent=cyan):
        shape = slide.shapes.add_shape(MSO_SHAPE.ROUNDED_RECTANGLE, Inches(x), Inches(y), Inches(w), Inches(h))
        shape.fill.solid()
        shape.fill.fore_color.rgb = panel
        shape.line.color.rgb = border

        marker = slide.shapes.add_shape(MSO_SHAPE.RECTANGLE, Inches(x), Inches(y), Inches(.06), Inches(h))
        marker.fill.solid()
        marker.fill.fore_color.rgb = accent
        marker.line.fill.background()

        add_text(slide, title.upper(), x + .16, y + .10, w - .28, .22, 8, True, accent)
        add_text(slide, value, x + .16, y + .34, w - .28, .35, 22, True, white)
        add_text(slide, subtitle, x + .16, y + .74, w - .28, .22, 8, False, muted)

    def add_bar_list(slide, title, items, x, y, w, h, accent=cyan, label_limit=42):
        shape = slide.shapes.add_shape(MSO_SHAPE.ROUNDED_RECTANGLE, Inches(x), Inches(y), Inches(w), Inches(h))
        shape.fill.solid()
        shape.fill.fore_color.rgb = panel
        shape.line.color.rgb = border
        add_text(slide, title, x + .16, y + .12, w - .32, .28, 12, True, white)

        if not items:
            add_text(slide, "Sem dados para os filtros atuais", x + .16, y + .55, w - .32, .3, 10, False, muted)
            return

        max_total = max([item.get("total") or 0 for item in items] + [1])
        current_y = y + .52
        step = min(.43, max(.31, (h - .75) / max(len(items[:8]), 1)))

        for item in items[:8]:
            label = clean_text(item.get("label") or "—", label_limit)
            total_item = item.get("total") or 0
            pct = (total_item / max_total) if max_total else 0

            add_text(slide, label, x + .16, current_y, w - .78, .18, 7.8, False, muted)
            add_text(slide, str(total_item), x + w - .50, current_y, .34, .18, 8, True, white)

            bar_bg = slide.shapes.add_shape(
                MSO_SHAPE.RECTANGLE,
                Inches(x + .16),
                Inches(current_y + .22),
                Inches(w - .50),
                Inches(.07),
            )
            bar_bg.fill.solid()
            bar_bg.fill.fore_color.rgb = RGBColor(30, 41, 59)
            bar_bg.line.fill.background()

            bar = slide.shapes.add_shape(
                MSO_SHAPE.RECTANGLE,
                Inches(x + .16),
                Inches(current_y + .22),
                Inches(max((w - .50) * pct, .03)),
                Inches(.07),
            )
            bar.fill.solid()
            bar.fill.fore_color.rgb = accent
            bar.line.fill.background()

            current_y += step

    def add_progress_panel(slide, title, chart, x, y, w, h, accent=cyan):
        add_bar_list(slide, title, chart, x, y, w, h, accent=accent, label_limit=36)

    def add_insight_box(slide, title, lines, x, y, w, h, accent=cyan):
        shape = slide.shapes.add_shape(MSO_SHAPE.ROUNDED_RECTANGLE, Inches(x), Inches(y), Inches(w), Inches(h))
        shape.fill.solid()
        shape.fill.fore_color.rgb = panel_2
        shape.line.color.rgb = border
        add_text(slide, title, x + .18, y + .15, w - .36, .3, 13, True, accent)

        current_y = y + .62
        for line in lines:
            add_text(slide, f"• {line}", x + .20, current_y, w - .38, .28, 9, False, white)
            current_y += .34

    health_color = green if saude_operacional >= 80 else orange if saude_operacional >= 55 else red
    health_label = "Saudável" if saude_operacional >= 80 else "Atenção" if saude_operacional >= 55 else "Crítico"

    # Slide 1: visão executiva
    slide = add_slide(
        "Dashboard Executivo KM",
        "Exportação PPTX enterprise com filtros aplicados ao dashboard",
    )
    add_text(slide, f"Filtros: {filtros_ativos}", .58, 1.10, 12.2, .24, 8, False, muted)

    add_card(slide, "Total filtrado", total, f"Base KM total: {total_km}", .55, 1.45)
    add_card(slide, "Recebidos", recebidos, f"{cobertura_recebimento}% de cobertura", 3.05, 1.45, accent=green)
    add_card(slide, "Pendentes TP", pendentes, "Recebidos sem Nº Transpetro", 5.55, 1.45, accent=orange if pendentes else green)
    add_card(slide, "Com N° Transpetro", com_tp, f"{cobertura_tp}% com TP", 8.05, 1.45, accent=green if com_tp else orange)
    add_card(slide, "Vínculo LD", f"{cobertura_vinculo}%", f"{km_com_ld} com Nº Transpetro / {total_ld} LD únicos", 10.55, 1.45, accent=green if cobertura_vinculo >= 80 else orange)

    add_card(
        slide,
        "Saúde operacional",
        f"{saude_operacional}%",
        f"{health_label} • 20% recebimento, 40% TP, 40% LD",
        .55,
        2.72,
        w=3.3,
        accent=health_color,
    )
    add_card(slide, "Sem Nº Transpetro", sem_tp, "Itens sem Nº Transpetro", 4.05, 2.72, w=2.55, accent=orange if sem_tp else green)
    add_card(slide, "Base LD", total_ld, "Arquivos únicos LD válidos", 6.82, 2.72, w=2.55, accent=blue)

    add_progress_panel(slide, "Recebimento", recebimento_chart, .55, 4.05, 3.7, 2.65, accent=green)
    add_progress_panel(slide, "Documento TP", tp_chart, 4.55, 4.05, 3.7, 2.65, accent=orange if sem_tp else green)
    add_progress_panel(slide, "Vínculo LD", vinculo_chart, 8.55, 4.05, 3.7, 2.65, accent=blue)

    # Slide 2: analytics operacionais
    slide = add_slide(
        "Analytics Operacionais KM",
        "Distribuição por disciplina, fase e matriz recebimento x TP",
    )
    add_bar_list(slide, "Por disciplina", disciplina_chart, .55, 1.25, 3.9, 2.55, accent=cyan, label_limit=36)
    add_bar_list(slide, "Por phase", phase_chart, 4.75, 1.25, 3.9, 2.55, accent=blue, label_limit=36)
    add_bar_list(slide, "Matriz recebimento x TP", matriz_recebimento_tp, 8.95, 1.25, 3.75, 2.55, accent=orange, label_limit=36)

    add_bar_list(slide, "Status KM", status_km_chart, .55, 4.25, 5.8, 2.55, accent=green, label_limit=52)
    add_bar_list(slide, "Top TOC", toc_chart, 6.75, 4.25, 5.95, 2.55, accent=cyan, label_limit=58)

    # Slide 3: leitura executiva
    slide = add_slide(
        "Leitura Executiva",
        "Resumo automático dos principais pontos de atenção",
    )

    insights = [
        f"{recebidos} de {total} itens filtrados possuem recebimento identificado.",
        f"{sem_tp} itens filtrados ainda não possuem documento TP associado.",
        f"Vínculo LD executivo: {cobertura_vinculo}% ({km_com_ld} com Nº Transpetro / {total_ld} LD únicos).",
        f"Saúde operacional ponderada: {saude_operacional}% ({health_label}).",
    ]
    add_insight_box(slide, "Principais sinais", insights, .65, 1.25, 5.95, 2.35, accent=health_color)

    acoes = []
    if sem_tp:
        acoes.append("Priorizar saneamento dos documentos sem TP.")
    if cobertura_vinculo < 80:
        acoes.append("Revisar vínculo LD executivo contra a base LD única válida.")
    if pendentes:
        acoes.append("Validar pendências de recebimento/transmittal.")
    if not acoes:
        acoes.append("Manter monitoramento e evolução dos analytics executivos.")

    add_insight_box(slide, "Ações recomendadas", acoes, 6.95, 1.25, 5.65, 2.35, accent=orange)

    add_bar_list(slide, "Status KM", status_km_chart, .65, 4.05, 5.8, 2.65, accent=green, label_limit=52)
    add_bar_list(slide, "Top TOC", toc_chart, 6.95, 4.05, 5.65, 2.65, accent=cyan, label_limit=54)

    output = BytesIO()
    prs.save(output)
    output.seek(0)

    response = HttpResponse(
        output.read(),
        content_type="application/vnd.openxmlformats-officedocument.presentationml.presentation",
    )
    response["Content-Disposition"] = 'attachment; filename="dashboard_km_executivo.pptx"'
    return response

def dashboard_km_ld(request):
    filtros = _km_filter_state(request)
    registros_base = DocumentoKM.objects.all()
    registros = _km_apply_filters(registros_base.order_by("numero_km"), filtros)

    if request.GET.get("export") == "pptx":
        return _km_exportar_dashboard_ppt(request)

    if request.GET.get("export") == "xlsx":
        return _km_exportar_excel_filtrado(registros)

    total = registros.count()
    total_km = registros_base.count()
    total_ld = _km_ld_base_unica_sem_marenova()
    total_transmittals = (
        registros.exclude(transmittal_numero="")
        .exclude(transmittal_numero__isnull=True)
        .values("transmittal_numero")
        .distinct()
        .count()
    )

    recebido_q = _km_recebido_q()
    recebidos = registros.filter(recebido_q).count()
    com_tp = registros.exclude(documento_tp="").exclude(documento_tp__isnull=True).count()

    # Regra operacional: recebido sem Nº Transpetro ainda é pendência.
    pendentes = max(recebidos - com_tp, 0)
    sem_tp = pendentes

    # Indicador executivo LD: Nº Transpetro sobre base LD única válida, sem Marenova.
    km_com_ld = com_tp
    km_sem_ld = max(total_ld - km_com_ld, 0)

    cobertura_recebimento = _km_pct(recebidos, total)
    cobertura_tp = _km_pct(com_tp, recebidos)
    cobertura_vinculo = _km_pct(km_com_ld, total_ld)
    saude_operacional = round(
        (cobertura_recebimento * 0.20)
        + (cobertura_tp * 0.40)
        + (cobertura_vinculo * 0.40),
        1,
    ) if total else 0

    if saude_operacional >= 80:
        saude_label = "Saudável"
        saude_class = "ok"
    elif saude_operacional >= 55:
        saude_label = "Atenção"
        saude_class = "warn"
    else:
        saude_label = "Crítico"
        saude_class = "danger"

    recentes = registros.order_by("-atualizado_em", "numero_km")[:10]

    query_params = request.GET.copy()
    query_params.pop("page", None)
    query_params.pop("export", None)

    context = {
        "documento_km_disponivel": True,
        "total": total,
        "total_km": total_km,
        "total_ld": total_ld,
        "total_transmittals": total_transmittals,
        "recebidos": recebidos,
        "pendentes": pendentes,
        "com_tp": com_tp,
        "sem_tp": sem_tp,
        "km_com_ld": km_com_ld,
        "km_sem_ld": km_sem_ld,
        "vinculados_ld": km_com_ld,
        "sem_vinculo_ld": km_sem_ld,
        "cobertura_recebimento": cobertura_recebimento,
        "cobertura_tp": cobertura_tp,
        "cobertura_vinculo": cobertura_vinculo,
        "saude_operacional": saude_operacional,
        "saude_label": saude_label,
        "saude_class": saude_class,
        "recentes": recentes,
        "disciplina_chart": _km_bar_chart(registros, "disciplina", 8),
        "phase_chart": _km_bar_chart(registros, "phase", 8),
        "toc_chart": _km_bar_chart(registros, "toc", 8),
        "status_km_chart": _km_bar_chart(registros, "status_km", 8),
        "status_recebimento_chart": _km_simple_chart([
            ("Recebidos", recebidos),
            ("Pendentes TP", pendentes),
        ]),
        "tp_chart": _km_simple_chart([
            ("Com Documento TP", com_tp),
            ("Sem Documento TP", sem_tp),
        ]),
        "matriz_recebimento_tp": [
            {"label": "Recebidos com TP", "total": registros.filter(recebido_q).exclude(documento_tp="").exclude(documento_tp__isnull=True).count()},
            {"label": "Recebidos sem TP", "total": registros.filter(recebido_q).filter(Q(documento_tp="") | Q(documento_tp__isnull=True)).count()},
            {"label": "Base LD única", "total": total_ld},
            {"label": "Vínculo LD %", "total": cobertura_vinculo},
        ],
        "phases": _km_distinct_values("phase"),
        "tocs": _km_distinct_values("toc"),
        "disciplinas": _km_distinct_values("disciplina"),
        "transmittals": _km_distinct_values("transmittal_numero"),
        "busca": filtros["busca"],
        "phases_selecionadas": filtros["phases"],
        "tocs_selecionados": filtros["tocs"],
        "disciplinas_selecionadas": filtros["disciplinas"],
        "transmittals_selecionados": filtros["transmittals"],
        "recebimentos_selecionados": filtros["recebimentos"],
        "tps_selecionados": filtros["tps"],
        "filtros_ativos": _km_active_filter_chips(filtros),
        "querystring": query_params.urlencode(),
    }

    return render(
        request,
        "automacoes/dashboard_km_ld.html",
        context,
    )


@login_required
def dashboard_excecoes_documentais(request):
    total_ld = DocumentoLD.objects.count()
    total_km = DocumentoKM.objects.count() if "DocumentoKM" in globals() else 0

    divergentes = 0
    sem_match = 0

    if _model_has_field(DocumentoLD, "status_revisao_km"):
        divergentes = DocumentoLD.objects.filter(
            status_revisao_km=getattr(DocumentoLD, "STATUS_REVISAO_KM_DIVERGENTE", "DIVERGENTE")
        ).count()

    if _model_has_field(DocumentoLD, "status_vinculo_km"):
        sem_match = DocumentoLD.objects.filter(
            status_vinculo_km=getattr(DocumentoLD, "STATUS_VINCULO_KM_SEM_MATCH", "SEM_MATCH")
        ).count()

    context = {
        "total_ld": total_ld,
        "total_km": total_km,
        "total_excecoes": divergentes + sem_match,
        "excecoes": [
            {"tipo": "Revisao KM divergente", "criticidade": "Alta", "quantidade": divergentes},
            {"tipo": "Sem vinculo KM", "criticidade": "Media", "quantidade": sem_match},
        ],
    }

    return render(request, "automacoes/dashboard_excecoes_documentais.html", context)
@login_required
def dashboard_alertas_operacionais(request):
    divergentes = 0
    sem_match = 0

    if _model_has_field(DocumentoLD, "status_revisao_km"):
        divergentes = DocumentoLD.objects.filter(
            status_revisao_km=getattr(DocumentoLD, "STATUS_REVISAO_KM_DIVERGENTE", "DIVERGENTE")
        ).count()

    if _model_has_field(DocumentoLD, "status_vinculo_km"):
        sem_match = DocumentoLD.objects.filter(
            status_vinculo_km=getattr(DocumentoLD, "STATUS_VINCULO_KM_SEM_MATCH", "SEM_MATCH")
        ).count()

    alertas = [
        {"tipo": "Divergencia de revisao", "criticidade": "Alta", "quantidade": divergentes},
        {"tipo": "Sem vinculo KM", "criticidade": "Media", "quantidade": sem_match},
    ]

    return render(
        request,
        "automacoes/dashboard_alertas_operacionais.html",
        {"alertas": alertas, "total_alertas": sum(a["quantidade"] for a in alertas)},
    )


@login_required
def listar_km(request):
    """
    Lista KM como espelho fiel da aba LD_KM importada.

    Mantém a operação KM sem inferência automática:
    - Documento TP vem apenas da planilha LD_KM.
    - Recebido/Pendente deriva de Transmittal Number ou Data recebimento KM.
    - Filtros usam multi-select via querystring repetida.
    """
    filtros = _km_filter_state(request)
    registros = _km_apply_filters(
        DocumentoKM.objects.all().order_by("numero_km"),
        filtros,
    )

    if request.GET.get("export") == "xlsx":
        return _km_exportar_excel_filtrado(registros)

    recebido_q = _km_recebido_q()
    base_total = DocumentoKM.objects.all()

    total = registros.count()
    total_km = base_total.count()
    total_recebidos = base_total.filter(recebido_q).count()
    total_pendentes = max(total_km - total_recebidos, 0)
    total_com_tp = base_total.exclude(documento_tp="").exclude(documento_tp__isnull=True).count()
    total_sem_tp = max(total_km - total_com_tp, 0)

    filtrados_recebidos = registros.filter(recebido_q).count()
    filtrados_pendentes = max(total - filtrados_recebidos, 0)
    filtrados_com_tp = registros.exclude(documento_tp="").exclude(documento_tp__isnull=True).count()
    filtrados_sem_tp = max(total - filtrados_com_tp, 0)

    paginator = Paginator(registros, 50)
    page_obj = paginator.get_page(request.GET.get("page"))

    query_params = request.GET.copy()
    query_params.pop("page", None)
    query_params.pop("export", None)

    # Compatibilidade com templates antigos e novos.
    phase = filtros["phases"][0] if filtros["phases"] else ""
    toc = filtros["tocs"][0] if filtros["tocs"] else ""
    disciplina = filtros["disciplinas"][0] if filtros["disciplinas"] else ""
    transmittal = filtros["transmittals"][0] if filtros["transmittals"] else ""
    recebimento = filtros["recebimentos"][0] if filtros["recebimentos"] else ""
    tp = filtros["tps"][0] if filtros["tps"] else ""

    return render(
        request,
        "automacoes/lista_km.html",
        {
            "registros": page_obj,
            "page_obj": page_obj,
            "busca": filtros["busca"],
            "phase": phase,
            "toc": toc,
            "disciplina": disciplina,
            "transmittal": transmittal,
            "recebimento": recebimento,
            "tp": tp,
            "phases_selecionadas": filtros["phases"],
            "tocs_selecionados": filtros["tocs"],
            "disciplinas_selecionadas": filtros["disciplinas"],
            "transmittals_selecionados": filtros["transmittals"],
            "recebimentos_selecionados": filtros["recebimentos"],
            "tps_selecionados": filtros["tps"],
            "filtros_ativos": _km_active_filter_chips(filtros),
            "total": total,
            "total_km": total_km,
            "total_recebidos": total_recebidos,
            "total_pendentes": total_pendentes,
            "total_com_tp": total_com_tp,
            "total_sem_tp": total_sem_tp,
            "total_vinculados": total_com_tp,
            "filtrados_recebidos": filtrados_recebidos,
            "filtrados_pendentes": filtrados_pendentes,
            "filtrados_com_tp": filtrados_com_tp,
            "filtrados_sem_tp": filtrados_sem_tp,
            "phases": _km_distinct_values("phase"),
            "tocs": _km_distinct_values("toc"),
            "disciplinas": _km_distinct_values("disciplina"),
            "transmittals": _km_distinct_values("transmittal_numero"),
            "querystring": query_params.urlencode(),
        },
    )


@login_required
def exportar_dashboard_pcfs_ppt(request):
    """
    Exporta apresentação executiva PCF em layout escuro D'ORANGE,
    respeitando os filtros ativos do Dashboard PCFs.
    """
    from collections import Counter
    from io import BytesIO

    from django.http import HttpResponse
    from pptx import Presentation
    from pptx.chart.data import CategoryChartData
    from pptx.dml.color import RGBColor
    from pptx.enum.chart import XL_CHART_TYPE
    from pptx.util import Inches, Pt

    registros = _pcf_enriquecer_runtime(list(_filtrar_pcfs_timeline(request)))

    total_pcfs = len(registros)
    total_open_docs = sum(1 for item in registros if (getattr(item, "open_comments", 0) or 0) > 0)
    total_open_comments = sum(getattr(item, "open_comments", 0) or 0 for item in registros)

    def _status(item):
        return str(getattr(item, "status_final", "") or "Sem status").strip() or "Sem status"

    def _tipo(item):
        return str(getattr(item, "tipo", "") or getattr(item, "tipo_documento", "") or "Sem tipo").strip() or "Sem tipo"

    def _doc(item):
        return str(
            getattr(item, "numero_documento", "")
            or getattr(item, "documento", "")
            or getattr(item, "codigo_documento", "")
            or "-"
        )

    def _rev(item):
        return str(getattr(item, "revisao_pcf", "") or getattr(item, "revisao", "") or "-")

    total_released = sum(1 for item in registros if _status(item).upper() == "RELEASED")
    total_released_comments = sum(1 for item in registros if _status(item).upper() == "RELEASED WITH COMMENTS")
    total_not_released = sum(1 for item in registros if _status(item).upper() == "NOT RELEASED")
    total_sla_vencido = sum(1 for item in registros if getattr(item, "sla_vencido_runtime", False))

    aging_valores = [
        getattr(item, "aging_dias_runtime", None)
        for item in registros
        if getattr(item, "aging_dias_runtime", None) is not None
    ]
    aging_medio = round(sum(aging_valores) / len(aging_valores), 1) if aging_valores else 0
    risco = round((total_not_released / total_pcfs) * 100, 1) if total_pcfs else 0
    sla_atendido = round(((total_pcfs - total_sla_vencido) / total_pcfs) * 100, 1) if total_pcfs else 100

    scores = [getattr(item, "criticidade_score_runtime", 0) or 0 for item in registros]
    risco_medio = round(sum(scores) / len(scores), 1) if scores else 0
    total_risco_critical = sum(1 for score in scores if score >= 80)
    total_risco_high = sum(1 for score in scores if score >= 60)
    released_ratio = round((total_released / total_pcfs) * 100, 1) if total_pcfs else 0

    filtros = []
    for key, label in [
        ("q", "Busca"),
        ("tipo", "Tipo"),
        ("status", "Status"),
        ("somente_latest", "Última revisão"),
        ("somente_open", "Apenas open"),
        ("com_comentarios", "Com comentários"),
        ("aging", "Aging"),
    ]:
        value = request.GET.get(key)
        if value not in (None, ""):
            filtros.append(f"{label}: {value}")
    filtros_txt = " | ".join(filtros) if filtros else "Sem filtros aplicados"

    prs = Presentation()
    prs.slide_width = Inches(13.333)
    prs.slide_height = Inches(7.5)

    BG = RGBColor(6, 13, 28)
    PANEL = RGBColor(14, 28, 52)
    PANEL_2 = RGBColor(18, 42, 72)
    CYAN = RGBColor(72, 190, 244)
    ORANGE = RGBColor(255, 161, 35)
    WHITE = RGBColor(245, 248, 255)
    MUTED = RGBColor(164, 188, 218)
    RED = RGBColor(255, 92, 92)
    GREEN = RGBColor(80, 220, 145)

    def add_bg(slide):
        shape = slide.shapes.add_shape(1, 0, 0, prs.slide_width, prs.slide_height)
        shape.fill.solid()
        shape.fill.fore_color.rgb = BG
        shape.line.fill.background()

    def add_title(slide, title, subtitle=None):
        box = slide.shapes.add_textbox(Inches(0.55), Inches(0.35), Inches(12.2), Inches(0.65))
        tf = box.text_frame
        tf.clear()
        p = tf.paragraphs[0]
        p.text = title
        p.font.bold = True
        p.font.size = Pt(28)
        p.font.color.rgb = WHITE
        if subtitle:
            sub = slide.shapes.add_textbox(Inches(0.58), Inches(0.98), Inches(11.8), Inches(0.35))
            stf = sub.text_frame
            stf.text = subtitle
            stf.paragraphs[0].font.size = Pt(10)
            stf.paragraphs[0].font.color.rgb = MUTED

    def add_footer(slide):
        line = slide.shapes.add_shape(1, Inches(0.5), Inches(7.08), Inches(12.3), Inches(0.02))
        line.fill.solid()
        line.fill.fore_color.rgb = ORANGE
        line.line.fill.background()
        foot = slide.shapes.add_textbox(Inches(0.55), Inches(7.12), Inches(12.1), Inches(0.25))
        foot.text_frame.text = f"GED_PROFISSIONAL • PCF Intelligence • {filtros_txt}"
        foot.text_frame.paragraphs[0].font.size = Pt(8)
        foot.text_frame.paragraphs[0].font.color.rgb = MUTED

    def add_card(slide, x, y, w, h, label, value, accent=CYAN):
        shp = slide.shapes.add_shape(5, Inches(x), Inches(y), Inches(w), Inches(h))
        shp.fill.solid()
        shp.fill.fore_color.rgb = PANEL
        shp.line.color.rgb = PANEL_2
        shp.line.width = Pt(1)
        stripe = slide.shapes.add_shape(1, Inches(x), Inches(y + h - 0.08), Inches(w), Inches(0.06))
        stripe.fill.solid()
        stripe.fill.fore_color.rgb = accent
        stripe.line.fill.background()
        t = slide.shapes.add_textbox(Inches(x + 0.16), Inches(y + 0.12), Inches(w - 0.32), Inches(0.25))
        t.text_frame.text = label.upper()
        t.text_frame.paragraphs[0].font.bold = True
        t.text_frame.paragraphs[0].font.size = Pt(8)
        t.text_frame.paragraphs[0].font.color.rgb = MUTED
        v = slide.shapes.add_textbox(Inches(x + 0.16), Inches(y + 0.44), Inches(w - 0.32), Inches(0.52))
        v.text_frame.text = str(value)
        v.text_frame.paragraphs[0].font.bold = True
        v.text_frame.paragraphs[0].font.size = Pt(22)
        v.text_frame.paragraphs[0].font.color.rgb = WHITE

    def add_text_block(slide, x, y, w, h, text):
        shp = slide.shapes.add_shape(5, Inches(x), Inches(y), Inches(w), Inches(h))
        shp.fill.solid()
        shp.fill.fore_color.rgb = PANEL
        shp.line.color.rgb = PANEL_2
        tb = slide.shapes.add_textbox(Inches(x + 0.25), Inches(y + 0.22), Inches(w - 0.5), Inches(h - 0.4))
        tf = tb.text_frame
        tf.word_wrap = True
        tf.text = text
        for p in tf.paragraphs:
            p.font.size = Pt(14)
            p.font.color.rgb = WHITE
        return tb

    def style_chart(chart):
        chart.has_legend = True
        chart.legend.include_in_layout = False
        chart.legend.font.size = Pt(8)
        chart.legend.font.color.rgb = MUTED
        chart.chart_title.has_text_frame = False
        try:
            chart.value_axis.tick_labels.font.size = Pt(8)
            chart.value_axis.tick_labels.font.color.rgb = MUTED
            chart.category_axis.tick_labels.font.size = Pt(8)
            chart.category_axis.tick_labels.font.color.rgb = MUTED
        except Exception:
            pass

    slide = prs.slides.add_slide(prs.slide_layouts[6])
    add_bg(slide)
    add_title(slide, "PCF Executive Intelligence", "Relatório executivo automático • D'ORANGE Platform")
    add_card(slide, 0.75, 2.0, 2.2, 1.15, "Total PCFs", total_pcfs, CYAN)
    add_card(slide, 3.15, 2.0, 2.2, 1.15, "Comentários abertos", total_open_comments, ORANGE)
    add_card(slide, 5.55, 2.0, 2.2, 1.15, "Not Released", total_not_released, RED)
    add_card(slide, 7.95, 2.0, 2.2, 1.15, "Risk Index", f"{risco_medio}", RED if risco_medio >= 70 else ORANGE)
    add_card(slide, 10.35, 2.0, 2.2, 1.15, "Released Ratio", f"{released_ratio}%", GREEN)
    narrativa = (
        f"A visão filtrada contém {total_pcfs} PCFs, com {total_open_docs} documentos contendo open comments "
        f"e {total_open_comments} comentários abertos. O aging médio é de {aging_medio} dias. "
        f"O índice médio de risco é {risco_medio}/100, com {total_risco_high} itens HIGH "
        f"e {total_risco_critical} itens CRITICAL."
    )
    add_text_block(slide, 0.75, 3.65, 11.8, 1.35, narrativa)
    add_footer(slide)

    slide = prs.slides.add_slide(prs.slide_layouts[6])
    add_bg(slide)
    add_title(slide, "Resumo Executivo", "Indicadores recalculados com os filtros ativos")
    cards = [
        ("Total PCFs", total_pcfs, CYAN),
        ("Com Open", total_open_docs, ORANGE),
        ("Comentários Abertos", total_open_comments, ORANGE),
        ("Released", total_released, GREEN),
        ("Rel. c/ Comments", total_released_comments, ORANGE),
        ("Not Released", total_not_released, RED),
        ("Risk Index", risco_medio, RED if risco_medio >= 70 else ORANGE),
        ("Released Ratio", f"{released_ratio}%", GREEN),
    ]
    for idx, (label, value, color) in enumerate(cards):
        x = 0.7 + (idx % 4) * 3.05
        y = 1.55 + (idx // 4) * 1.55
        add_card(slide, x, y, 2.75, 1.15, label, value, color)
    add_footer(slide)

    slide = prs.slides.add_slide(prs.slide_layouts[6])
    add_bg(slide)
    add_title(slide, "Distribuição por Status", "Quantidade de PCFs por status final")
    def _status_norm(item):
        status = _status(item).strip()
        return status.upper() if status else "SEM STATUS"

    status_counts = Counter(_status_norm(item) for item in registros)
    chart_data = CategoryChartData()
    chart_data.categories = list(status_counts.keys()) or ["Sem dados"]
    chart_data.add_series("PCFs", list(status_counts.values()) or [0])
    chart = slide.shapes.add_chart(
        XL_CHART_TYPE.COLUMN_CLUSTERED,
        Inches(0.8), Inches(1.45), Inches(11.8), Inches(4.85),
        chart_data,
    ).chart
    style_chart(chart)
    add_footer(slide)

    slide = prs.slides.add_slide(prs.slide_layouts[6])
    add_bg(slide)
    add_title(slide, "Distribuição por Tipo", "Volume documental PCF por tipo")
    tipo_counts = Counter(_tipo(item) for item in registros)
    top_tipos = tipo_counts.most_common(8)
    chart_data = CategoryChartData()
    chart_data.categories = [k for k, _ in top_tipos] or ["Sem dados"]
    chart_data.add_series("PCFs", [v for _, v in top_tipos] or [0])
    chart = slide.shapes.add_chart(
        XL_CHART_TYPE.BAR_CLUSTERED,
        Inches(1.0), Inches(1.35), Inches(11.3), Inches(5.0),
        chart_data,
    ).chart
    style_chart(chart)
    add_footer(slide)

    slide = prs.slides.add_slide(prs.slide_layouts[6])
    add_bg(slide)
    add_title(slide, "Top Pendências", "Ranking por criticidade operacional runtime")
    top = sorted(
        registros,
        key=lambda x: (
            getattr(x, "criticidade_score_runtime", 0) or 0,
            int(getattr(x, "open_comments", 0) or 0),
            getattr(x, "aging_dias_runtime", 0) or 0,
        ),
        reverse=True,
    )[:10]
    rows = len(top) + 1
    cols = 7
    table_shape = slide.shapes.add_table(rows, cols, Inches(0.35), Inches(1.35), Inches(12.65), Inches(5.35))
    table = table_shape.table
    headers = ["Documento", "Rev", "Open", "Aging", "Status", "Risco", "Classe"]
    widths = [3.0, 0.65, 0.75, 0.8, 3.35, 0.75, 1.05]
    for c, width in enumerate(widths):
        table.columns[c].width = Inches(width)
    for c, head in enumerate(headers):
        cell = table.cell(0, c)
        cell.text = head
        cell.fill.solid()
        cell.fill.fore_color.rgb = PANEL_2
        p = cell.text_frame.paragraphs[0]
        p.font.bold = True
        p.font.size = Pt(8)
        p.font.color.rgb = WHITE
    for r, item in enumerate(top, start=1):
        values = [
            _doc(item),
            _rev(item),
            str(getattr(item, "open_comments", 0) or 0),
            str(getattr(item, "aging_dias_runtime", None) if getattr(item, "aging_dias_runtime", None) is not None else "-"),
            _status(item),
            str(getattr(item, "criticidade_score_runtime", 0) or 0),
            str(getattr(item, "criticidade_faixa_runtime", "") or "-"),
        ]
        for c, value in enumerate(values):
            cell = table.cell(r, c)
            cell.text = value[:55]
            cell.fill.solid()
            cell.fill.fore_color.rgb = PANEL
            p = cell.text_frame.paragraphs[0]
            p.font.size = Pt(7.5)
            p.font.color.rgb = WHITE if c != 4 else MUTED
    add_footer(slide)

    slide = prs.slides.add_slide(prs.slide_layouts[6])
    add_bg(slide)
    add_title(slide, "Snapshot Operacional", "Leitura executiva da carteira PCF filtrada")
    if total_pcfs:
        texto = (
            f"Base filtrada: {total_pcfs} PCFs.\n\n"
            f"Pontos de atenção: {total_not_released} documentos NOT RELEASED, "
            f"{total_sla_vencido} registros com SLA vencido e {total_open_comments} comentários abertos.\n\n"
            f"Risco executivo: Risk Index {risco_medio}/100, com {total_risco_high} itens HIGH "
            f"e {total_risco_critical} itens CRITICAL. Released Ratio atual: {released_ratio}%.\n\n"
            f"Prioridade recomendada: tratar os itens HIGH/CRITICAL do Top Pendências, reduzindo open comments "
            f"e acelerando a conversão para RELEASED."
        )
    else:
        texto = "Nenhum registro encontrado para os filtros aplicados."
    add_text_block(slide, 0.8, 1.45, 11.7, 4.8, texto)
    add_footer(slide)

    output = BytesIO()
    prs.save(output)
    output.seek(0)

    response = HttpResponse(
        output.read(),
        content_type="application/vnd.openxmlformats-officedocument.presentationml.presentation",
    )
    response["Content-Disposition"] = 'attachment; filename="pcf_executive_report.pptx"'
    return response

# PPT footer enhancement placeholder: Gerado em runtime.
