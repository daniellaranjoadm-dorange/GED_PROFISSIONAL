from pathlib import Path
import time

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.conf import settings
from django.utils import timezone
from django.core.paginator import Paginator
from django.db.models import Avg, Count, Q, Sum
from django.http import FileResponse, Http404, HttpResponse
from django.shortcuts import redirect, render
from openpyxl import Workbook
from openpyxl.styles import Font, PatternFill

from apps.automacoes.models import TransmittalKM, PCFTimeline, DocumentoLD, ExecucaoAutomacao
from apps.automacoes.services import (
    atualizar_ld,
    grd_ghenova,
    timeline_pcfs,
    transmittal_km,
)



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


@login_required
def painel(request):
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

    ultimos_pcfs = PCFTimeline.objects.order_by("-atualizado_em")[:5] if _model_has_field(PCFTimeline, "atualizado_em") else PCFTimeline.objects.all()[:5]
    ultimos_transmittals = TransmittalKM.objects.order_by("-criado_em")[:5] if _model_has_field(TransmittalKM, "criado_em") else TransmittalKM.objects.all()[:5]

    ultima_atualizacao = (
        _latest_model_value(PCFTimeline, "atualizado_em", "criado_em")
        or _latest_model_value(TransmittalKM, "criado_em", "atualizado_em")
        or _latest_model_value(DocumentoLD, "atualizado_em", "criado_em")
    )

    ultimas_execucoes = ExecucaoAutomacao.objects.select_related("usuario").order_by("-iniciado_em")[:8]
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

    return render(
        request,
        "automacoes/painel.html",
        {
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
        },
    )


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

    return redirect("automacoes:painel")


@login_required
def logs_automacoes(request):
    busca = request.GET.get("q", "").strip()
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


@login_required
def listar_transmittals_km(request):
    busca = request.GET.get("q", "").strip()
    pasta = request.GET.get("pasta", "").strip()
    emissao = request.GET.get("emissao", "").strip()
    transmittal = request.GET.get("transmittal", "").strip()

    registros = TransmittalKM.objects.all().order_by("-criado_em")

    if busca:
        registros = registros.filter(
            Q(documento__icontains=busca)
            | Q(titulo__icontains=busca)
            | Q(transmittal_numero__icontains=busca)
        )

    if pasta:
        registros = registros.filter(pasta__iexact=pasta)

    if emissao:
        registros = registros.filter(emissao__iexact=emissao)

    if transmittal:
        registros = registros.filter(transmittal_numero__iexact=transmittal)

    return render(
        request,
        "automacoes/transmittals_km.html",
        {
            "registros": registros,
            "busca": busca,
            "pasta": pasta,
            "emissao": emissao,
            "transmittal": transmittal,
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




def _filtrar_pcfs_timeline(request):
    busca = request.GET.get("q", "").strip()
    tipo = request.GET.get("tipo", "").strip()
    status = request.GET.get("status", "").strip()
    somente_open = request.GET.get("somente_open", "").strip()

    registros = PCFTimeline.objects.all().order_by(
        "numero_documento",
        "revisao_pcf",
        "pcf_link",
    )

    if busca:
        registros = (
            registros.filter(numero_documento__icontains=busca)
            | registros.filter(numero_pcf__icontains=busca)
            | registros.filter(pcf_link__icontains=busca)
            | registros.filter(titulo__icontains=busca)
        )

    if tipo:
        registros = registros.filter(tipo=tipo)

    if status:
        registros = registros.filter(status_final__iexact=status)

    if somente_open:
        registros = registros.filter(open_comments__gt=0)

    return registros

@login_required
def listar_pcfs_timeline(request):
    busca = request.GET.get("q", "").strip()
    tipo = request.GET.get("tipo", "").strip()
    status = request.GET.get("status", "").strip()
    somente_open = request.GET.get("somente_open", "").strip()

    registros = _filtrar_pcfs_timeline(request)

    tipos = (
        PCFTimeline.objects.exclude(tipo="")
        .values_list("tipo", flat=True)
        .distinct()
        .order_by("tipo")
    )

    total = registros.count()
    total_open = registros.filter(open_comments__gt=0).count()
    total_sem_status = registros.filter(status_final="").count()

    paginator = Paginator(registros, 50)
    page_number = request.GET.get("page")
    page_obj = paginator.get_page(page_number)

    return render(
        request,
        "automacoes/pcfs_timeline.html",
        {
            "registros": page_obj,
            "page_obj": page_obj,
            "busca": busca,
            "tipo": tipo,
            "status": status,
            "somente_open": somente_open,
            "tipos": tipos,
            "total": total,
            "total_open": total_open,
            "total_sem_status": total_sem_status,
        },
    )

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
    registros = _filtrar_pcfs_timeline(request)

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
    registros = PCFTimeline.objects.all()

    total = registros.count()
    total_open = registros.filter(open_comments__gt=0).count()
    total_sem_status = registros.filter(status_final="").count()
    total_not_released = registros.filter(status_final__icontains="NOT RELEASED").count()
    total_released = registros.filter(status_final__icontains="RELEASED").exclude(
        status_final__icontains="NOT RELEASED"
    ).count()

    total_comentarios_abertos = (
        registros.aggregate(total=Sum("open_comments")).get("total") or 0
    )

    por_tipo = list(
        registros.values("tipo")
        .annotate(total=Count("id"), open_total=Sum("open_comments"))
        .order_by("-total", "tipo")
    )

    por_status = list(
        registros.values("status_final")
        .annotate(total=Count("id"))
        .order_by("-total")[:10]
    )

    top_pendencias = (
        registros.filter(open_comments__gt=0)
        .order_by("-open_comments", "numero_documento")[:15]
    )

    recentes = registros.order_by("-atualizado_em")[:10]

    status_chart_labels = [(item.get("status_final") or "Sem status") for item in por_status]
    status_chart_values = [item.get("total") or 0 for item in por_status]

    tipo_chart_labels = [(item.get("tipo") or "Sem tipo") for item in por_tipo]
    tipo_chart_values = [item.get("total") or 0 for item in por_tipo]

    tipo_open_labels = [(item.get("tipo") or "Sem tipo") for item in por_tipo]
    tipo_open_values = [item.get("open_total") or 0 for item in por_tipo]

    critical_rate = round((total_not_released / total) * 100, 1) if total else 0

    return render(
        request,
        "automacoes/dashboard_pcfs.html",
        {
            "total": total,
            "total_open": total_open,
            "total_sem_status": total_sem_status,
            "total_not_released": total_not_released,
            "total_released": total_released,
            "total_comentarios_abertos": total_comentarios_abertos,
            "critical_rate": critical_rate,
            "por_tipo": por_tipo,
            "por_status": por_status,
            "top_pendencias": top_pendencias,
            "recentes": recentes,
            "status_chart_labels": status_chart_labels,
            "status_chart_values": status_chart_values,
            "tipo_chart_labels": tipo_chart_labels,
            "tipo_chart_values": tipo_chart_values,
            "tipo_open_labels": tipo_open_labels,
            "tipo_open_values": tipo_open_values,
        },
    )



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
    texto = _ld_texto(revisao).upper()

    if not texto:
        return -1

    if texto.isdigit():
        return int(texto)

    peso = 0
    for char in texto:
        if "A" <= char <= "Z":
            peso = peso * 26 + (ord(char) - ord("A") + 1)

    return 1000 + peso


def _ld_filtrar_ultimas_revisoes(queryset):
    dados = list(queryset.values_list("pk", "documento", "revisao"))

    ultimos = {}

    for pk, documento, revisao in dados:
        doc = _ld_texto(documento).upper()
        peso = _ld_revisao_peso(revisao)

        if doc not in ultimos or peso > ultimos[doc][0]:
            ultimos[doc] = (peso, pk)

    ids = [pk for _, pk in ultimos.values()]

    return queryset.filter(pk__in=ids)


def _ld_filtrar_queryset(request):
    busca = _ld_texto(request.GET.get("q"))
    origem = _ld_texto(request.GET.get("origem"))
    disciplina = _ld_texto(request.GET.get("disciplina"))
    status_doc = _ld_texto(request.GET.get("status_doc"))
    status_grd = _ld_texto(request.GET.get("status_grd"))
    status_pcf = _ld_texto(request.GET.get("status_pcf"))

    com_pcf = _ld_bool(request.GET.get("com_pcf"))
    sem_pcf = _ld_bool(request.GET.get("sem_pcf"))
    com_resposta = _ld_bool(request.GET.get("com_resposta"))
    ultimas_revisoes = _ld_bool(request.GET.get("ultimas_revisoes"))

    filtro_rapido = _ld_texto(request.GET.get("filtro"))

    if filtro_rapido == "recebidos":
        status_doc = "Recebido"
    elif filtro_rapido == "aprovados":
        status_doc = "Aprovado"
    elif filtro_rapido == "grd_emitido":
        status_grd = "Emitido"
    elif filtro_rapido == "com_pcf":
        com_pcf = True
    elif filtro_rapido == "sem_pcf":
        sem_pcf = True
    elif filtro_rapido == "com_resposta":
        com_resposta = True
    elif filtro_rapido == "not_released":
        status_pcf = "NOT RELEASED"
    elif filtro_rapido == "ultimas_revisoes":
        ultimas_revisoes = True

    registros = DocumentoLD.objects.all().order_by("documento", "revisao")

    registros = _ld_filtrar_origem(registros, origem)

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

    if disciplina:
        registros = registros.filter(disciplina__icontains=disciplina)

    if status_doc:
        registros = registros.filter(status_documento__iexact=status_doc)

    if status_grd:
        registros = registros.filter(status_grd__iexact=status_grd)

    if status_pcf:
        status_pcf_norm = status_pcf.strip().upper()
        if status_pcf_norm in ["RELEASED", "NOT RELEASED"]:
            registros = registros.filter(status_final_pcf__iexact=status_pcf)
        else:
            registros = registros.filter(status_final_pcf__icontains=status_pcf)

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
        "origem": origem,
        "disciplina": disciplina,
        "status_doc": status_doc,
        "status_grd": status_grd,
        "status_pcf": status_pcf,
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


def _ld_caminhos_candidatos(caminho_salvo):
    bruto = _ld_texto(caminho_salvo).split("#", 1)[0].replace("/", "\\")
    candidatos = []

    if not bruto:
        return candidatos

    candidatos.append(Path(bruto))

    partes = [p for p in bruto.split("\\") if p and p not in {".", ".."}]

    base_path = _ld_texto(getattr(settings, "LD_BASE_PATH", ""))

    bases = []
    if base_path:
        bases.append(Path(base_path))

    user_home = Path.home()
    bases.extend([
        Path.cwd(),
        user_home,
        user_home / "Documents",
        user_home / "OneDrive",
        user_home / "Desktop",
    ])

    for base in bases:
        candidatos.append(base / Path(*partes))

    # Quando o caminho vem como ../9 - PCFs..., a raiz deve ser a pasta acima de 1/9/10.
    if base_path and partes:
        candidatos.append(Path(base_path) / Path(*partes))

    unicos = []
    vistos = set()

    for candidato in candidatos:
        texto = str(candidato)
        if texto not in vistos:
            vistos.add(texto)
            unicos.append(candidato)

    return unicos


def _ld_resolver_caminho(caminho_salvo):
    candidatos = _ld_caminhos_candidatos(caminho_salvo)

    for candidato in candidatos:
        if candidato.exists():
            return candidato, candidatos

    return None, candidatos


def _ld_hyperlink(caminho):
    arquivo, _ = _ld_resolver_caminho(caminho)
    if arquivo:
        return arquivo.resolve().as_uri()
    return _ld_texto(caminho)



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
    query_string = query_params.urlencode()

    return render(
        request,
        "automacoes/lista_ld.html",
        {
            "registros": page_obj,
            "page_obj": page_obj,
            "query_string": query_string,

            "origens": origens,
            "disciplinas": disciplinas,
            "status_documentos": status_documentos,
            "status_grds": status_grds,

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



@login_required
def dashboard_ld(request):
    registros = DocumentoLD.objects.all()

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

    por_disciplina = list(
        registros.values("disciplina")
        .annotate(total=Count("id"))
        .order_by("-total")[:12]
    )

    por_origem = list(
        registros.values("origem_aba")
        .annotate(total=Count("id"))
        .order_by("-total")
    )

    por_status_documento = list(
        registros.values("status_documento")
        .annotate(total=Count("id"))
        .order_by("-total")[:10]
    )

    por_status_grd = list(
        registros.values("status_grd")
        .annotate(total=Count("id"))
        .order_by("-total")[:10]
    )

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

    disciplina_labels = [
        item.get("disciplina") or "Sem disciplina"
        for item in por_disciplina
    ]
    disciplina_values = [
        item.get("total") or 0
        for item in por_disciplina
    ]

    origem_labels = [
        item.get("origem_aba") or "Sem origem"
        for item in por_origem
    ]
    origem_values = [
        item.get("total") or 0
        for item in por_origem
    ]

    status_doc_labels = [
        item.get("status_documento") or "Sem status"
        for item in por_status_documento
    ]
    status_doc_values = [
        item.get("total") or 0
        for item in por_status_documento
    ]

    status_grd_labels = [
        item.get("status_grd") or "Sem status"
        for item in por_status_grd
    ]
    status_grd_values = [
        item.get("total") or 0
        for item in por_status_grd
    ]

    pcf_labels = ["Com PCF", "Sem PCF", "Com resposta", "Sem resposta"]
    pcf_values = [
        kpis["total_com_pcf"],
        kpis["total_sem_pcf"],
        kpis["total_com_resposta"],
        total_sem_resposta,
    ]

    taxa_pcf = 0
    if kpis["total"]:
        taxa_pcf = round((kpis["total_com_pcf"] / kpis["total"]) * 100, 1)

    taxa_grd = 0
    if kpis["total"]:
        taxa_grd = round((kpis["total_emitidos"] / kpis["total"]) * 100, 1)

    taxa_aprovacao = 0
    if kpis["total"]:
        taxa_aprovacao = round((kpis["total_aprovados"] / kpis["total"]) * 100, 1)

    return render(
        request,
        "automacoes/dashboard_ld.html",
        {
            **kpis,
            "total_not_released": total_not_released,
            "total_released": total_released,
            "total_sem_status_doc": total_sem_status_doc,
            "total_sem_grd": total_sem_grd,
            "total_sem_resposta": total_sem_resposta,
            "taxa_pcf": taxa_pcf,
            "taxa_grd": taxa_grd,
            "taxa_aprovacao": taxa_aprovacao,
            "por_disciplina": por_disciplina,
            "por_origem": por_origem,
            "por_status_documento": por_status_documento,
            "por_status_grd": por_status_grd,
            "top_disciplinas_pendentes": top_disciplinas_pendentes,
            "top_not_released": top_not_released,
            "recentes": recentes,
            "disciplina_labels": disciplina_labels,
            "disciplina_values": disciplina_values,
            "origem_labels": origem_labels,
            "origem_values": origem_values,
            "status_doc_labels": status_doc_labels,
            "status_doc_values": status_doc_values,
            "status_grd_labels": status_grd_labels,
            "status_grd_values": status_grd_values,
            "pcf_labels": pcf_labels,
            "pcf_values": pcf_values,
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
        html += "<p>Configure no <strong>settings.py</strong>:</p>"
        html += '<pre>LD_BASE_PATH = r"C:\\CAMINHO\\DA\\PASTA\\RAIZ"</pre>'
        html += "<p>A raiz deve conter as pastas anteriores a <strong>1 - DOCS EMISSÃO ENGEDOC</strong>, <strong>9 - PCFs Transpetro</strong> e <strong>10 - Engenharia</strong>.</p>"

        return HttpResponse(html, status=404)

    if arquivo.is_dir():
        html = "<h3>Pasta localizada.</h3>"
        html += f"<p><strong>Caminho:</strong> {arquivo}</p>"
        html += "<p>Por segurança, navegadores não abrem pasta local diretamente via Django.</p>"
        html += "<p>Copie o caminho acima e cole no Windows Explorer.</p>"

        return HttpResponse(html)

    return FileResponse(
        open(arquivo, "rb"),
        as_attachment=False,
        filename=arquivo.name,
    )

