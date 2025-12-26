from django.shortcuts import render, redirect, get_object_or_404
from django.core.files.storage import default_storage
from django.contrib.auth import authenticate, login, logout
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.db.models import Count, Q, Sum
from django.utils import timezone
from django.http import HttpResponse, JsonResponse
from django.core.paginator import Paginator
from django.contrib.auth.models import Group
from datetime import date, datetime
from io import BytesIO
from django.db.models import Q
from django.shortcuts import render
from django.shortcuts import get_object_or_404, redirect
from django.contrib import messages
from django.contrib.auth.decorators import login_required
import csv
import json
import os
import re
from difflib import unified_diff

import openpyxl
from openpyxl.styles import Font, Alignment, PatternFill, Border, Side
from openpyxl.utils import get_column_letter

from apps.contas.permissions import has_perm
from apps.contas.decorators import allow_admin

from .models import (
    Projeto,
    Documento,
    ArquivoDocumento,
    DocumentoVersao,
    ResponsavelDisciplina,
    WorkflowEtapa,
    DocumentoWorkflowStatus,
    LogAuditoria,
    ProjetoFinanceiro,
    DocumentoAprovacao,   # ★ AGORA IMPORTADO ★
    registrar_log,
)

from .utils_email import enviar_email
# ==============================================================
# DEFINIÇÃO OFICIAL DAS ETAPAS DO WORKFLOW (CODIFICADAS)
# ==============================================================

ETAPAS_WORKFLOW = [
    "ELABORACAO",
    "REVISAO_INTERNA",
    "APROVACAO_TECNICA",
    "DOC_CONTROL",
    "ENVIADO_CLIENTE",
    "APROVACAO_CLIENTE",
    "EMISSAO_FINAL",
]

ETAPAS_LABEL = {
    "ELABORACAO": "Elaboração",
    "REVISAO_INTERNA": "Revisão Interna – Disciplina",
    "APROVACAO_TECNICA": "Aprovação Técnica – Coordenador",
    "DOC_CONTROL": "Doc Control",
    "ENVIADO_CLIENTE": "Envio ao Cliente",
    "APROVACAO_CLIENTE": "Aprovação do Cliente",
    "EMISSAO_FINAL": "Emissão Final",
}

# =================================================================
# CONFIG GLOBAL
# =================================================================

from decimal import Decimal  # <-- garante precisão nos valores em dólar/reais

VALOR_MEDICAO_USD = Decimal("979.00")  # ainda usado na medição genérica
TAXA_CAMBIO_REAIS = Decimal("5.7642")  # taxa fixa que você passou

# =================================================================
# FUNÇÕES AUXILIARES – ENTERPRISE S7
# =================================================================

def normalizar_revisao(rev_bruto):
    """Normaliza revisões e valida formatos aceitos."""
    if rev_bruto is None:
        return ""

    rev = str(rev_bruto).strip().upper()

    if rev == "":
        return ""
    if rev == "0":
        return "0"
    if rev.isdigit():
        return None
    if any(ch.isdigit() for ch in rev):
        return None

    if rev.startswith("R") and rev[1:].isalpha():
        return rev[1:]

    return rev if rev.isalpha() else None


def highlight_text(texto, termo):
    """Destaca termo com <mark> (case-insensitive)."""
    if not texto or not termo:
        return texto or ""

    regex = re.compile(re.escape(termo), re.IGNORECASE)

    def repl(match):
        return (
            "<mark style='background:#ffeb3b; padding:2px; border-radius:4px;'>"
            f"{match.group(0)}</mark>"
        )

    return regex.sub(repl, texto)


def usuario_em_grupos(user, grupos):
    """Verifica se usuario pertence a qualquer grupo da lista."""
    if not user.is_authenticated:
        return False
    return user.groups.filter(name__in=grupos).exists()


# -------------------------------------------------------------
# PERMISSÕES – BASEADAS EM WorkflowEtapa (objeto), não strings
# -------------------------------------------------------------

def pode_avancar_etapa(user, documento: Documento):
    """Verifica se o usuário pode avançar o documento para a próxima etapa."""

    if user.is_superuser:
        return True

    # Controle central: grupo Doc-Control sempre pode avançar
    doc_control = usuario_em_grupos(user, ["DOC_CONTROL", "Doc-Control", "DOC CONTROL"])

    if doc_control:
        return True

    # Se não há etapa definida ainda → permitido avançar para a primeira etapa
    if documento.etapa is None:
        return True

    # Se a etapa tem grupos responsáveis definidos
    grupos = documento.etapa.grupos_responsaveis.all()

    if grupos:
        return user.groups.filter(id__in=grupos).exists()

    # Se não há restrição configurada → libera avanço
    return True


def pode_retornar_etapa(user, documento: Documento):
    """Permissão para retornar etapa."""
    if user.is_superuser:
        return True

    # Doc-Control sempre pode retornar
    if usuario_em_grupos(user, ["DOC_CONTROL", "DOC CONTROL", "Doc-Control"]):
        return True

    # Coordenadores (COORD_*) também podem
    if user.groups.filter(name__startswith="COORD_").exists():
        return True

    return False


# -------------------------------------------------------------
# WORKFLOW ENTERPRISE — PRÓXIMA / ANTERIOR
# -------------------------------------------------------------

def proxima_etapa(documento):
    """
    Retorna a próxima etapa configurada no Workflow Enterprise.
    """

    # Sem etapa → assume a primeira
    if documento.etapa is None:
        return WorkflowEtapa.objects.filter(ativa=True).order_by("ordem").first()

    # Próxima etapa declarada no admin
    if documento.etapa.proxima_etapa:
        return documento.etapa.proxima_etapa

    # Fallback: próxima pela ordem
    return (
        WorkflowEtapa.objects.filter(
            ativa=True, ordem__gt=documento.etapa.ordem
        ).order_by("ordem").first()
    )


def etapa_anterior(documento: Documento):
    """
    Retorna a etapa anterior à atual, baseada na ordem.
    """

    if documento.etapa is None:
        return None

    return (
        WorkflowEtapa.objects.filter(
            ativa=True, ordem__lt=documento.etapa.ordem
        ).order_by("-ordem").first()
    )


# -------------------------------------------------------------
# REGISTRO DE WORKFLOW (LOG)
# -------------------------------------------------------------

def registrar_workflow(documento: Documento, etapa, acao: str = "", request=None, observacao: str = "", **kwargs):
    """
    Registra movimentação no log enterprise.
    'etapa' agora é WorkflowEtapa ou string com nome.
    """

    # Compatibilidade: versões antigas chamavam registrar_workflow(..., status="...")
    if not acao:
        acao = (kwargs.get("status") or "").strip()

    if request is None:
        raise ValueError("registrar_workflow requer request")

    if isinstance(etapa, str):
        etapa_obj = WorkflowEtapa.objects.filter(nome=etapa).first()
    else:
        etapa_obj = etapa

    usuario = request.user if request.user.is_authenticated else None

    descricao = (
        f"[WORKFLOW] Documento {documento.codigo} "
        f"→ {etapa_obj.nome if etapa_obj else etapa} | "
        f"Ação: {acao} | {observacao or ''}"
    )

    registrar_log(
        usuario,
        documento,
        f"Workflow: {acao}",
        descricao
    )


# -------------------------------------------------------------
# NOTIFICAÇÕES
# -------------------------------------------------------------

def notificar_evento_documento(documento: Documento, tipo_evento: str):
    """Centraliza notificações por e-mail."""
    assunto = ""
    mensagem = ""

    if tipo_evento == "envio_revisao":
        assunto = f"Documento em Revisão: {documento.codigo}"
        mensagem = (
            f"O documento {documento.codigo} (Rev {documento.revisao}) "
            "foi enviado para revisão."
        )
    elif tipo_evento == "aprovacao":
        assunto = f"Documento Aprovado: {documento.codigo}"
        mensagem = (
            f"O documento {documento.codigo} (Rev {documento.revisao}) "
            "foi aprovado."
        )
    elif tipo_evento == "emissao":
        assunto = f"Documento Emitido: {documento.codigo}"
        mensagem = (
            f"O documento {documento.codigo} (Rev {documento.revisao}) "
            f"foi emitido em {documento.data_emissao_grdt}."
        )
    elif tipo_evento == "cancelamento":
        assunto = f"Documento Cancelado: {documento.codigo}"
        mensagem = (
            f"O documento {documento.codigo} (Rev {documento.revisao}) "
            "foi cancelado."
        )
    else:
        return

    try:
        enviar_email(
            assunto=assunto,
            mensagem=mensagem,
            destinatarios=["seu.email@empresa.com"],
        )
    except:
        pass


# -------------------------------------------------------------
# LIXEIRA
# -------------------------------------------------------------

def mover_para_lixeira(documento: Documento, request, motivo: str = ""):
    """Soft delete enterprise."""
    if not documento.ativo:
        return False

    documento.ativo = False
    documento.deletado_em = timezone.now()
    documento.deletado_por = request.user.username
    documento.motivo_exclusao = motivo or ""
    documento.save()

    registrar_workflow(documento, documento.etapa, "Excluído", request, motivo)
    return True


def restaurar_da_lixeira(documento: Documento, request):
    documento.ativo = True
    documento.deletado_em = None
    documento.deletado_por = None
    documento.motivo_exclusao = ""
    documento.save()

    registrar_workflow(documento, documento.etapa, "Restaurado", request)


# =================================================================
# DASHBOARD SIMPLES
# =================================================================

@login_required
def dashboard(request):
    docs = Documento.objects.filter(ativo=True)

    total_docs = docs.count()
    total_aprovados = docs.filter(status_documento="Aprovado").count()
    total_em_revisao = docs.filter(status_documento="Em Revisão").count()
    total_emitidos = docs.filter(status_emissao="Emitido").count()
    total_nao_recebidos = docs.filter(status_emissao="Não Recebido").count()

    valor_emitidos_usd = total_emitidos * VALOR_MEDICAO_USD
    valor_nao_rec_usd = total_nao_recebidos * VALOR_MEDICAO_USD
    valor_total_usd = valor_emitidos_usd + valor_nao_rec_usd

    return render(
        request,
        "documentos/dashboard.html",
        {
            "total_docs": total_docs,
            "total_aprovados": total_aprovados,
            "total_em_revisao": total_em_revisao,
            "total_emitidos": total_emitidos,
            "total_nao_recebidos": total_nao_recebidos,
            "valor_total_usd": f"{valor_total_usd:,.2f}",
        },
    )


# =================================================================
# DASHBOARD ENTERPRISE
# =================================================================

@login_required
@has_perm("sistema.dashboard_enterprise")
def dashboard_enterprise(request):
    docs = Documento.objects.filter(ativo=True).select_related("projeto")

    filtros = {
        "projeto": request.GET.get("projeto") or "",
        "disciplina": request.GET.get("disciplina") or "",
        "tipo_doc": request.GET.get("tipo_doc") or "",
        "status_documento": request.GET.get("status_ldp") or "",
        "status_emissao": request.GET.get("status_emissao") or "",
        "dt_ini": request.GET.get("dt_ini") or "",
        "dt_fim": request.GET.get("dt_fim") or "",
    }

    if filtros["projeto"]:
        docs = docs.filter(projeto__nome__icontains=filtros["projeto"])

    if filtros["disciplina"]:
        docs = docs.filter(disciplina=filtros["disciplina"])

    if filtros["tipo_doc"]:
        docs = docs.filter(tipo_doc=filtros["tipo_doc"])

    if filtros["status_documento"]:
        docs = docs.filter(status_documento=filtros["status_documento"])

    if filtros["status_emissao"]:
        docs = docs.filter(status_emissao=filtros["status_emissao"])

    if filtros["dt_ini"]:
        dt_ini = datetime.strptime(filtros["dt_ini"], "%Y-%m-%d").date()
        docs = docs.filter(data_emissao_grdt__gte=dt_ini)

    if filtros["dt_fim"]:
        dt_fim = datetime.strptime(filtros["dt_fim"], "%Y-%m-%d").date()
        docs = docs.filter(data_emissao_grdt__lte=dt_fim)

    total_docs = docs.count()
    total_emitidos = docs.filter(status_emissao="Emitido").count()
    total_nao_recebidos = docs.filter(status_emissao="Não Recebido").count()
    total_em_revisao = docs.filter(status_documento="Em Revisão").count()
    total_aprovados = docs.filter(status_documento="Aprovado").count()

    valor_emitidos_usd = total_emitidos * VALOR_MEDICAO_USD
    valor_nao_rec_usd = total_nao_recebidos * VALOR_MEDICAO_USD
    valor_total_usd = valor_emitidos_usd + valor_nao_rec_usd

    valor_emitidos_brl = valor_emitidos_usd * TAXA_CAMBIO_REAIS
    valor_nao_rec_brl = valor_nao_rec_usd * TAXA_CAMBIO_REAIS
    valor_total_brl = valor_emitidos_brl + valor_nao_rec_brl

    por_disc = docs.values("disciplina").annotate(qtd=Count("id"))
    disc_labels = [d["disciplina"] or "Sem Disciplina" for d in por_disc]
    disc_data = [d["qtd"] for d in por_disc]

    por_status = docs.values("status_documento").annotate(qtd=Count("id"))
    status_labels = [d["status_documento"] or "Sem Status" for d in por_status]
    status_data = [d["qtd"] for d in por_status]

    med_raw = docs.values("tipo_doc").annotate(
        total=Count("id"),
        emitidos=Count("id", filter=Q(status_emissao="Emitido")),
        nr=Count("id", filter=Q(status_emissao="Não Recebido")),
    )

    medicao_linhas = []
    total_usd = 0
    total_brl = 0

    for m in med_raw:
        tipo = m["tipo_doc"] or "Sem Tipo"
        emit = m["emitidos"]
        nr = m["nr"]

        v_emit_usd = emit * VALOR_MEDICAO_USD
        v_nr_usd = nr * VALOR_MEDICAO_USD
        v_emit_brl = v_emit_usd * TAXA_CAMBIO_REAIS
        v_nr_brl = v_nr_usd * TAXA_CAMBIO_REAIS

        total_usd += v_emit_usd + v_nr_usd
        total_brl += v_emit_brl + v_nr_brl

        medicao_linhas.append(
            {
                "tipo_doc": tipo,
                "total": m["total"],
                "emitidos": emit,
                "nao_recebidos": nr,
                "valor_emitidos_usd": f"{v_emit_usd:,.2f}",
                "valor_nr_usd": f"{v_nr_usd:,.2f}",
                "valor_emitidos_brl": f"{v_emit_brl:,.2f}",
                "valor_nr_brl": f"{v_nr_brl:,.2f}",
            }
        )

    medicao_totais = {
        "total_docs": sum(m["total"] for m in med_raw),
        "total_usd": f"{total_usd:,.2f}",
        "total_brl": f"{total_brl:,.2f}",
    }

    base_qs = Documento.objects.filter(ativo=True).select_related("projeto")

    return render(
        request,
        "documentos/dashboard_enterprise.html",
        {
            "filtros": filtros,
            "total_docs": total_docs,
            "total_emitidos": total_emitidos,
            "total_nao_recebidos": total_nao_recebidos,
            "total_em_revisao": total_em_revisao,
            "total_aprovados": total_aprovados,
            "valor_emitidos_usd": f"{valor_emitidos_usd:,.2f}",
            "valor_emitidos_brl": f"{valor_emitidos_brl:,.2f}",
            "valor_nao_rec_usd": f"{valor_nao_rec_usd:,.2f}",
            "valor_nao_rec_brl": f"{valor_nao_rec_brl:,.2f}",
            "valor_total_usd": f"{valor_total_usd:,.2f}",
            "valor_total_brl": f"{valor_total_brl:,.2f}",
            "disc_labels": json.dumps(disc_labels),
            "disc_data": json.dumps(disc_data),
            "status_labels": json.dumps(status_labels),
            "status_data": json.dumps(status_data),
            "medicao_linhas": medicao_linhas,
            "medicao_totais": medicao_totais,
            "lista_projetos": base_qs.values_list("projeto__nome", flat=True).distinct(),
            "lista_disciplinas": base_qs.values_list("disciplina", flat=True).distinct(),
            "lista_tipos": base_qs.values_list("tipo_doc", flat=True).distinct(),
            "lista_status_ldp": base_qs.values_list("status_documento", flat=True).distinct(),
            "lista_status_emissao": base_qs.values_list("status_emissao", flat=True).distinct(),
        },
    )


# =================================================================
# PAINEL DE WORKFLOW
# =================================================================

@login_required
def painel_workflow(request):
    docs_base = Documento.objects.filter(ativo=True).select_related("projeto")

    etapa_filtro = request.GET.get("etapa") or ""
    disciplina_filtro = request.GET.get("disciplina") or ""
    projeto_filtro = request.GET.get("projeto") or ""
    status_ldp_filtro = request.GET.get("status_ldp") or ""
    status_emissao_filtro = request.GET.get("status_emissao") or ""

    docs = docs_base

    if etapa_filtro and etapa_filtro != "Sem etapa":
        docs = docs.filter(etapa_atual=etapa_filtro)
    elif etapa_filtro == "Sem etapa":
        docs = docs.filter(Q(etapa_atual__isnull=True) | Q(etapa_atual=""))

    if disciplina_filtro:
        docs = docs.filter(disciplina=disciplina_filtro)

    if projeto_filtro:
        docs = docs.filter(projeto__nome=projeto_filtro)

    if status_ldp_filtro:
        docs = docs.filter(status_documento=status_ldp_filtro)

    if status_emissao_filtro:
        docs = docs.filter(status_emissao=status_emissao_filtro)

    order = request.GET.get("order") or ""
    direction = request.GET.get("direction") or "asc"

    valid_fields = {
        "codigo": "codigo",
        "titulo": "titulo",
        "disciplina": "disciplina",
        "projeto": "projeto__nome",
        "etapa_atual": "etapa_atual",
        "status_ldp": "status_documento",
        "status_emissao": "status_emissao",
        "revisao": "revisao",
    }

    if order in valid_fields:
        field = valid_fields[order]
        if direction == "desc":
            field = "-" + field
        docs = docs.order_by(field)
    else:
        docs = docs.order_by("etapa__ordem", "codigo")

    disciplinas = (
        docs_base.exclude(disciplina__isnull=True)
        .exclude(disciplina__exact="")
        .values_list("disciplina", flat=True)
        .distinct()
        .order_by("disciplina")
    )

    projetos = (
        docs_base.filter(projeto__isnull=False)
        .values_list("projeto__nome", flat=True)
        .distinct()
        .order_by("projeto__nome")
    )

    status_ldp_lista = (
        docs_base.exclude(status_documento__isnull=True)
        .exclude(status_documento__exact="")
        .values_list("status_documento", flat=True)
        .distinct()
        .order_by("status_documento")
    )

    status_emissao_lista = (
        docs_base.exclude(status_emissao__isnull=True)
        .exclude(status_emissao__exact="")
        .values_list("status_emissao", flat=True)
        .distinct()
        .order_by("status_emissao")
    )

    per_page = request.GET.get("per_page") or 25
    try:
        per_page = int(per_page)
    except ValueError:
        per_page = 25

    total_filtrados = docs.count()

    paginator = Paginator(docs, per_page)
    page_number = request.GET.get("page")
    page_obj = paginator.get_page(page_number)
    documentos = page_obj

    por_etapa_qs = docs_base.values("etapa_atual").annotate(qtd=Count("id"))
    mapa_etapas = {row["etapa_atual"] or "Sem etapa": row["qtd"] for row in por_etapa_qs}

    etapas_kpi = []
    for nome in ETAPAS_WORKFLOW:
        url = (
            f"?etapa={nome}"
            f"&disciplina={disciplina_filtro}"
            f"&projeto={projeto_filtro}"
            f"&status_ldp={status_ldp_filtro}"
            f"&status_emissao={status_emissao_filtro}"
            f"&order={order}"
            f"&direction={direction}"
            f"&per_page={per_page}"
        )
        etapas_kpi.append(
            {
                "nome": nome,
                "qtd": mapa_etapas.get(nome, 0),
                "url": url,
            }
        )

    url_sem_etapa = (
        f"?etapa=Sem%20etapa"
        f"&disciplina={disciplina_filtro}"
        f"&projeto={projeto_filtro}"
        f"&status_ldp={status_ldp_filtro}"
        f"&status_emissao={status_emissao_filtro}"
        f"&order={order}"
        f"&direction={direction}"
        f"&per_page={per_page}"
    )

    etapas_kpi.append(
        {
            "nome": "Sem etapa definida",
            "qtd": mapa_etapas.get("Sem etapa", mapa_etapas.get(None, 0)),
            "url": url_sem_etapa,
        }
    )

    ultimos_movimentos = (
        DocumentoAprovacao.objects
        .select_related("documento", "etapa", "usuario")
        .order_by("-data")[:20]
    )

    return render(
        request,
        "documentos/painel_workflow.html",
        {
            "documentos": documentos,
            "page_obj": page_obj,
            "per_page": per_page,
            "total_docs": total_filtrados,
            "order": order,
            "direction": direction,
            "etapas_kpi": etapas_kpi,
            "etapas_workflow": ETAPAS_WORKFLOW,
            "etapa_filtro": etapa_filtro,
            "disciplinas": disciplinas,
            "disciplina_filtro": disciplina_filtro,
            "projetos": projetos,
            "projeto_filtro": projeto_filtro,
            "status_ldp_lista": status_ldp_lista,
            "status_ldp_filtro": status_ldp_filtro,
            "status_emissao_lista": status_emissao_lista,
            "status_emissao_filtro": status_emissao_filtro,
            "ultimos_movimentos": ultimos_movimentos,
        },
    )


# =================================================================
# EXPORTAR EXCEL DO PAINEL
# =================================================================

@login_required
def painel_workflow_exportar_excel(request):
    etapa = request.GET.get("etapa") or ""
    disciplina = request.GET.get("disciplina") or ""
    projeto = request.GET.get("projeto") or ""
    status_ldp = request.GET.get("status_ldp") or ""
    status_emissao = request.GET.get("status_emissao") or ""

    docs = Documento.objects.filter(ativo=True).select_related("projeto")

    if etapa and etapa != "Sem etapa":
        docs = docs.filter(etapa_atual=etapa)
    elif etapa == "Sem etapa":
        docs = docs.filter(Q(etapa_atual__isnull=True) | Q(etapa_atual=""))

    if disciplina:
        docs = docs.filter(disciplina=disciplina)
    if projeto:
        docs = docs.filter(projeto__nome=projeto)
    if status_ldp:
        docs = docs.filter(status_documento=status_ldp)
    if status_emissao:
        docs = docs.filter(status_emissao=status_emissao)

    wb = openpyxl.Workbook()
    ws = wb.active
    ws.title = "Workflow GED"

    headers = [
        "Código",
        "Revisão",
        "Título",
        "Disciplina",
        "Projeto",
        "Etapa Atual",
        "Status Documento",
        "Status Emissão",
    ]
    ws.append(headers)

    header_fill = PatternFill(start_color="0052A2", end_color="0052A2", fill_type="solid")
    border = Border(
        left=Side(style="thin"),
        right=Side(style="thin"),
        top=Side(style="thin"),
        bottom=Side(style="thin"),
    )

    for col in ws[1]:
        col.fill = header_fill
        col.font = Font(color="FFFFFF", bold=True)
        col.border = border
        col.alignment = Alignment(horizontal="center")

    for d in docs:
        ws.append(
            [
                d.codigo or "",
                d.revisao or "",
                d.titulo or "",
                d.disciplina or "",
                d.projeto.nome if d.projeto else "",
                d.etapa_atual or "",
                d.status_documento or "",
                d.status_emissao or "",
            ]
        )

    for column_cells in ws.columns:
        length = max(len(str(cell.value)) if cell.value else 0 for cell in column_cells)
        ws.column_dimensions[column_cells[0].column_letter].width = length + 3

    output = BytesIO()
    wb.save(output)
    output.seek(0)

    filename = f"workflow_{date.today().isoformat()}.xlsx"

    return HttpResponse(
        output.getvalue(),
        content_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )
# =====================================================================
# 📁 LISTA DE DOCUMENTOS – com filtros funcionando 100%
# =====================================================================
def listar_documentos(request):
    # Base: só documentos ativos e não deletados
    documentos = Documento.objects.filter(ativo=True, deletado_em__isnull=True)

    # ---- Filtros vindos da barra superior ----
    projeto_filtro        = request.GET.get("projeto", "") or ""
    disciplina_filtro     = request.GET.get("disciplina", "") or ""
    status_doc_filtro     = request.GET.get("status_documento", "") or ""
    status_emissao_filtro = request.GET.get("status_emissao", "") or ""
    busca                 = request.GET.get("busca", "") or ""

    # Aplica filtros
    if projeto_filtro:
        documentos = documentos.filter(projeto__nome__icontains=projeto_filtro)

    if disciplina_filtro:
        documentos = documentos.filter(disciplina__icontains=disciplina_filtro)

    if status_doc_filtro:
        documentos = documentos.filter(status_documento__icontains=status_doc_filtro)

    if status_emissao_filtro:
        documentos = documentos.filter(status_emissao__icontains=status_emissao_filtro)

    # 🔥 CORREÇÃO DEFINITIVA DA BUSCA GLOBAL
    if busca:
        documentos = documentos.filter(
            Q(codigo__icontains=busca) |
            Q(titulo__icontains=busca)
        )

    # ---- Combos dos selects (usados no template listar.html) ----
    projetos = (
        Documento.objects
        .values_list("projeto__nome", flat=True)
        .exclude(projeto__nome__isnull=True)
        .exclude(projeto__nome__exact="")
        .distinct()
        .order_by("projeto__nome")
    )

    disciplinas = (
        Documento.objects
        .values_list("disciplina", flat=True)
        .exclude(disciplina__isnull=True)
        .exclude(disciplina__exact="")
        .distinct()
        .order_by("disciplina")
    )

    status_documento_list = (
        Documento.objects
        .values_list("status_documento", flat=True)
        .exclude(status_documento__isnull=True)
        .exclude(status_documento__exact="")
        .distinct()
        .order_by("status_documento")
    )

    status_emissao_list = (
        Documento.objects
        .values_list("status_emissao", flat=True)
        .exclude(status_emissao__isnull=True)
        .exclude(status_emissao__exact="")
        .distinct()
        .order_by("status_emissao")
    )

    # ---- Contexto para o template listar.html ----
    context = {
        "documentos": documentos,
        "projetos": projetos,
        "disciplinas": disciplinas,
        "status_documento_list": status_documento_list,
        "status_emissao_list": status_emissao_list,
    }

    return render(request, "documentos/listar.html", context)

# ==============================
# Revisões permitidas no sistema
# ==============================
REVISOES_VALIDAS = ["0"] + [chr(i) for i in range(ord("A"), ord("Z")+1)]

# =================================================================
# DETALHE DO DOCUMENTO
# =================================================================

@login_required
def detalhes_documento(request, documento_id):
    documento = get_object_or_404(
        Documento.objects.select_related("projeto", "etapa"), id=documento_id
    )

    anexos = list(documento.arquivos.all())
    for a in anexos:
        try:
            a.url_absoluta = request.build_absolute_uri(a.arquivo.url)
        except Exception:
            a.url_absoluta = a.arquivo.url

    versoes_qs = documento.versoes.all().order_by("-criado_em")
    versao_atual = versoes_qs.first()

    rev_atual = str(documento.revisao or "").strip().upper()
    if rev_atual not in REVISOES_VALIDAS:
        rev_atual = "0"

    try:
        idx = REVISOES_VALIDAS.index(rev_atual)
        proxima_revisao = (
            REVISOES_VALIDAS[idx + 1]
            if idx + 1 < len(REVISOES_VALIDAS)
            else rev_atual
        )
    except ValueError:
        proxima_revisao = "A"

    workflow_status = getattr(documento, "workflow_status", None)

    context = {
        "documento": documento,
        "anexos": anexos,
        "versoes": versoes_qs,
        "versao_atual": versao_atual,
        "proxima_revisao": proxima_revisao,
        "workflow_status": workflow_status,
        "pode_avancar_etapa": pode_avancar_etapa(request.user, documento),
        "proxima_etapa": proxima_etapa(documento),
        "pode_retornar_etapa": pode_retornar_etapa(request.user, documento),
        "etapa_anterior": etapa_anterior(documento),
        "historico_workflow": documento.historico_workflow.select_related(
            "etapa", "usuario"
        ).order_by("-data"),
    }

    return render(request, "documentos/detalhes.html", context)


# =================================================================
# HISTÓRICO POR CÓDIGO
# =================================================================

@login_required
def historico(request, codigo):
    documentos = Documento.objects.filter(codigo=codigo).order_by("-revisao")
    versoes = (
        DocumentoVersao.objects.filter(documento__codigo=codigo)
        .select_related("documento", "criado_por")
        .order_by("-criado_em")
    )
    return render(
        request,
        "documentos/historico.html",
        {"documentos": documentos, "versoes": versoes, "codigo": codigo},
    )


# =================================================================
# AVANÇAR / RETORNAR ETAPA — WORKFLOW ENTERPRISE (COM OBS + ANEXOS)
# =================================================================

@login_required
def enviar_proxima_etapa(request, documento_id):
    documento = get_object_or_404(Documento, id=documento_id)

    if request.method != "POST":
        messages.error(request, "Requisição inválida.")
        return redirect("documentos:detalhes_documento", documento_id=documento.id)

    if not pode_avancar_etapa(request.user, documento):
        messages.error(request, "Você não tem permissão para avançar esta etapa.")
        return redirect("documentos:detalhes_documento", documento_id=documento.id)

    observacao = (request.POST.get("observacao") or "").strip()
    anexos = request.FILES.getlist("anexos")

    if not observacao:
        messages.warning(request, "Informe o motivo/observação para avançar a etapa.")
        return redirect("documentos:detalhes_documento", documento_id=documento.id)

    nova_etapa = documento.enviar_para_proxima_etapa(
        usuario=request.user,
        observacao=observacao,
        anexos=anexos,
    )

    if not nova_etapa:
        messages.warning(request, "Este documento já está na última etapa do workflow.")
        return redirect("documentos:detalhes_documento", documento_id=documento.id)

    registrar_workflow(documento, nova_etapa, "Avançou etapa", request, observacao)
    messages.success(request, f"Documento avançado para: {nova_etapa.nome}")
    return redirect("documentos:detalhes_documento", documento_id=documento.id)


@login_required
def retornar_etapa(request, documento_id):
    documento = get_object_or_404(Documento, id=documento_id)

    if request.method != "POST":
        messages.error(request, "Requisição inválida.")
        return redirect("documentos:detalhes_documento", documento_id=documento.id)

    if not pode_retornar_etapa(request.user, documento):
        messages.error(request, "Sem permissão para retornar etapa.")
        return redirect("documentos:detalhes_documento", documento_id=documento.id)

    observacao = (request.POST.get("observacao") or request.POST.get("motivo") or "").strip()
    anexos = request.FILES.getlist("anexos")

    if not observacao:
        messages.warning(request, "Informe o motivo/observação para retornar a etapa.")
        return redirect("documentos:detalhes_documento", documento_id=documento.id)

    destino = etapa_anterior(documento)
    if not destino:
        messages.warning(request, "Documento já está na primeira etapa.")
        return redirect("documentos:detalhes_documento", documento_id=documento.id)

    documento.retornar_etapa(
        etapa_destino=destino,
        usuario=request.user,
        motivo=observacao,
        anexos=anexos,
    )

    registrar_workflow(documento, destino, "Retornou etapa", request, observacao)
    messages.success(request, f"Documento retornado para: {destino.nome}")
    return redirect("documentos:detalhes_documento", documento_id=documento.id)
def nova_versao(request, documento_id):
    documento = get_object_or_404(Documento, id=documento_id)

    rev_atual = str(documento.revisao or "").strip().upper()
    if rev_atual not in REVISOES_VALIDAS:
        rev_atual = "0"
    try:
        idx = REVISOES_VALIDAS.index(rev_atual)
        proxima_revisao = (
            REVISOES_VALIDAS[idx + 1] if idx + 1 < len(REVISOES_VALIDAS) else rev_atual
        )
    except ValueError:
        proxima_revisao = "A"

    if request.method == "POST":
        numero_revisao = request.POST.get("numero_revisao", "").strip().upper()
        observacao = request.POST.get("observacao", "").strip()
        arquivo = request.FILES.get("arquivo")

        if not arquivo:
            messages.error(request, "Selecione um arquivo.")
            return redirect("documentos:detalhes_documento", documento_id=documento.id)

        if not numero_revisao:
            numero_revisao = proxima_revisao

        if numero_revisao not in REVISOES_VALIDAS:
            messages.error(request, "Revisão inválida.")
            return redirect("documentos:detalhes_documento", documento_id=documento.id)

        DocumentoVersao.objects.create(
            documento=documento,
            numero_revisao=numero_revisao,
            arquivo=arquivo,
            observacao=observacao,
            criado_por=request.user,
            status_revisao="REVISAO",
        )

        documento.revisao = numero_revisao
        documento.save(update_fields=["revisao"])

        registrar_workflow(
            documento,
            etapa="Nova Versão",
            acao="Criada",
            request=request,
            observacao=f"Versão {numero_revisao} adicionada.",
        )

        messages.success(request, "Nova versão adicionada com sucesso!")
        return redirect("documentos:detalhes_documento", documento_id=documento.id)

    return redirect("documentos:detalhes_documento", documento_id=documento.id)

# =================================================================
# UPLOAD DOCUMENTO (CRIAR)
# =================================================================
import logging
logger = logging.getLogger(__name__)

@login_required
@has_perm("documento.criar")
def upload_documento(request):
    if request.method == "POST":
        revisao = normalizar_revisao(request.POST.get("revisao"))
        if revisao is None:
            messages.error(request, "Revisão inválida!")
            return redirect("documentos:upload_documento")
        revisao = revisao or "0"

        titulo = (request.POST.get("titulo") or "").strip()
        codigo = (request.POST.get("codigo") or "").strip()
        if not titulo or not codigo:
            messages.error(request, "Preencha Título e Código.")
            return redirect("documentos:upload_documento")

        # projeto (opcional)
        projeto = None
        projeto_id = (request.POST.get("projeto") or "").strip()
        if projeto_id:
            projeto = Projeto.objects.filter(id=projeto_id, ativo=True).first()

        if not projeto:
            projeto = Projeto.objects.filter(ativo=True).order_by("id").first()

        if not projeto:
            messages.error(request, "Cadastre ao menos 1 Projeto antes de criar documentos.")
            return redirect("documentos:upload_documento")

        # cria documento (independente do upload)
        doc = Documento.objects.create(
            projeto=projeto,
            titulo=titulo,
            codigo=codigo,
            revisao=revisao,
            disciplina=((request.POST.get("disciplina") or "").strip() or None),
            tipo_doc=((request.POST.get("tipo_doc") or "").strip() or None),
            fase=((request.POST.get("fase") or "").strip() or ""),
            ativo=True,
            deletado_em=None,
        )

        # arquivos: "arquivos" (multiple) ou "arquivo" (single)
        arquivos = request.FILES.getlist("arquivos") or []
        if not arquivos:
            unico = request.FILES.get("arquivo")
            if unico:
                arquivos = [unico]

        anexados = 0
        falha_storage = False

        for arq in arquivos:
            try:
                ArquivoDocumento.objects.create(
                    documento=doc,
                    arquivo=arq,  # R2/S3 PutObject
                    nome_original=getattr(arq, "name", None),
                    tipo=(arq.name.split(".")[-1].lower() if getattr(arq, "name", "") else None),
                )
                anexados += 1
            except Exception:
                falha_storage = True
                logger.exception("Falha ao salvar anexo no storage (R2/S3)")
                break

        # workflow (não pode derrubar)
        try:
            registrar_workflow(doc, "Criação", "Criado", request)
        except Exception:
            logger.exception("Falha ao registrar workflow")

        # auditoria (não usa montar_descricao_log -> evita NameError)
        try:
            usuario = getattr(request.user, "username", None) or getattr(request.user, "email", None) or str(request.user)
            descricao = f"{usuario} criou o documento {doc.codigo} (Rev {doc.revisao}) - {doc.titulo}"
            registrar_log(request.user, doc, "Criação de Documento", descricao)
        except Exception:
            logger.exception("Falha ao registrar log de auditoria")

        if falha_storage:
            messages.warning(
                request,
                "Documento criado, mas falhou o upload do arquivo (R2 Unauthorized). "
                "Corrija as credenciais/permissões do R2 no Railway."
            )
        elif anexados == 0 and arquivos:
            messages.warning(request, "Documento criado, mas sem anexos.")
        else:
            messages.success(request, f"Documento criado com sucesso! ({anexados} arquivo(s))")

        return redirect("documentos:listar_documentos")

    projetos = Projeto.objects.filter(ativo=True).order_by("nome")
    return render(
        request,
        "documentos/upload.html",
        {"projetos": projetos, "REVISOES_VALIDAS": REVISOES_VALIDAS},
    )


# =================================================================
# EDITAR DOCUMENTO
# =================================================================

@login_required
@has_perm("documento.editar")
def editar_documento(request, documento_id):
    documento = get_object_or_404(Documento, id=documento_id)

    if request.method == "POST":
        revisao = normalizar_revisao(request.POST.get("revisao"))
        if revisao is None:
            messages.error(request, "Revisão inválida.")
            return redirect("documentos:editar_documento", documento_id=documento.id)

        projeto_id = request.POST.get("projeto")
        if projeto_id:
            try:
                projeto = Projeto.objects.get(id=projeto_id)
                documento.projeto = projeto
            except Projeto.DoesNotExist:
                messages.error(request, "Projeto inválido.")
                return redirect("documentos:editar_documento", documento_id=documento.id)

        documento.fase = request.POST.get("fase") or ""
        documento.tipo_doc = request.POST.get("tipo_doc") or ""
        documento.codigo = request.POST.get("codigo") or ""
        documento.disciplina = request.POST.get("disciplina") or ""
        documento.titulo = request.POST.get("titulo") or ""
        documento.status_documento = request.POST.get("status_documento") or ""
        documento.status_emissao = request.POST.get("status_emissao") or ""
        documento.grdt_cliente = request.POST.get("grdt_cliente") or ""
        documento.resposta_cliente = request.POST.get("resposta_cliente") or ""
        documento.ged_interna = request.POST.get("ged_interna") or ""
        documento.revisao = revisao

        data_emissao_grdt = request.POST.get("data_emissao_grdt") or ""
        if data_emissao_grdt:
            try:
                documento.data_emissao_grdt = datetime.strptime(
                    data_emissao_grdt, "%Y-%m-%d"
                ).date()
            except ValueError:
                messages.error(request, "Data de emissão GRDT inválida.")
                return redirect("documentos:editar_documento", documento_id=documento.id)
        else:
            documento.data_emissao_grdt = None

        documento.save()

        messages.success(request, "Documento atualizado.")
        return redirect("documentos:detalhes_documento", documento_id=documento.id)

    projetos = Projeto.objects.filter(ativo=True).order_by("nome")
    return render(
        request,
        "documentos/editar.html",
        {
            "documento": documento,
            "projetos": projetos,
            "REVISOES_VALIDAS": REVISOES_VALIDAS,
        },
    )


# =================================================================
# NOVA REVISÃO (WORKFLOW)
# =================================================================

import logging
logger = logging.getLogger(__name__)

@login_required
@has_perm("documento.revisar")
def nova_revisao(request, documento_id):
    documento = get_object_or_404(Documento, id=documento_id)

    idx = REVISOES_VALIDAS.index(documento.revisao) if documento.revisao in REVISOES_VALIDAS else -1
    nova_rev = REVISOES_VALIDAS[idx + 1] if idx + 1 < len(REVISOES_VALIDAS) else "A"

    if request.method == "POST":
        arquivo = request.FILES.get("arquivo")
        observacao = request.POST.get("observacao", "")

        if not arquivo:
            messages.error(request, "Envie o arquivo da nova revisão.")
            return redirect("documentos:detalhes_documento", documento_id=documento.id)

        try:
            DocumentoVersao.objects.create(
                documento=documento,
                numero_revisao=nova_rev,
                arquivo=arquivo,  # chama storage aqui
                criado_por=request.user,
                observacao=observacao,
                status_revisao="REVISAO",
            )
        except Exception:
            logger.exception("Falha ao salvar nova revisão no storage (R2/S3)")
            messages.error(
                request,
                "Falha ao enviar o arquivo da nova revisão (storage/R2 Unauthorized). "
                "A revisão do documento NÃO foi alterada."
            )
            return redirect("documentos:detalhes_documento", documento_id=documento.id)

        documento.revisao = nova_rev
        documento.status_documento = "Em Revisão"
        documento.save(update_fields=["revisao", "status_documento"])

        registrar_workflow(documento, "Nova Revisão", "Criado", request)
        notificar_evento_documento(documento, "envio_revisao")

        messages.success(request, f"Revisão {nova_rev} criada com sucesso!")
        return redirect("documentos:detalhes_documento", documento_id=documento.id)

    return render(
        request,
        "documentos/nova_revisao.html",
        {"documento": documento, "proxima_revisao": nova_rev},
    )


# =================================================================
# UPLOAD DE ANEXOS
# =================================================================

import logging
logger = logging.getLogger(__name__)

@login_required
def adicionar_arquivos(request, documento_id):
    documento = get_object_or_404(Documento, id=documento_id)

    if request.method == "POST":
        # suporta <input name="arquivos" multiple> e fallback <input name="arquivo">
        arquivos = request.FILES.getlist("arquivos") or []
        if not arquivos:
            unico = request.FILES.get("arquivo")
            if unico:
                arquivos = [unico]

        if not arquivos:
            messages.error(request, "Selecione ao menos 1 arquivo.")
            return redirect("documentos:detalhes_documento", documento_id=documento.id)

        anexados = 0
        falhas = 0

        for arq in arquivos:
            try:
                ArquivoDocumento.objects.create(
                    documento=documento,
                    arquivo=arq,  # aqui o R2/S3 tenta PutObject
                    nome_original=getattr(arq, "name", None),
                    tipo=(arq.name.split(".")[-1].lower() if getattr(arq, "name", "") else None),
                )
                anexados += 1
            except Exception:
                falhas += 1
                logger.exception("Falha ao salvar anexo no storage (R2/S3)")

        # não deixa o workflow derrubar a tela
        try:
            registrar_workflow(
                documento,
                "Upload de anexos",
                "Arquivos adicionados" if anexados else "Falha no upload",
                request,
                observacao=f"{anexados} ok / {falhas} falha(s)",
            )
        except Exception:
            logger.exception("Falha ao registrar_workflow em adicionar_arquivos")

        if anexados and falhas:
            messages.warning(request, f"{anexados} arquivo(s) enviados, {falhas} falharam (R2 Unauthorized).")
        elif anexados:
            messages.success(request, "Arquivos enviados com sucesso!")
        else:
            messages.error(
                request,
                "Falhou o envio dos arquivos (R2/S3 Unauthorized). "
                "O documento continua, mas sem anexos. Corrija o R2 no Railway."
            )

        return redirect("documentos:detalhes_documento", documento_id=documento.id)

    return render(request, "documentos/adicionar_arquivos.html", {"documento": documento})

# =================================================================
# EXCLUIR ARQUIVO INDIVIDUAL
# =================================================================

@login_required
def excluir_arquivo(request, arquivo_id):
    arq = get_object_or_404(ArquivoDocumento, id=arquivo_id)
    documento_id = arq.documento.id

    try:
        default_storage.delete(arq.arquivo.name)
    except Exception:
        pass

    arq.delete()

    messages.success(request, "Arquivo excluído com sucesso.")
    return redirect("documentos:detalhes_documento", documento_id=documento_id)


# =================================================================
# WORKFLOW DE EMISSÃO / APROVAÇÃO
# =================================================================

@login_required
def enviar_para_revisao(request, documento_id):
    documento = get_object_or_404(Documento, id=documento_id)

    documento.status_documento = "Em Revisão"
    documento.save(update_fields=["status_documento"])

    registrar_workflow(documento, "Revisão Interna – Disciplina", "Enviado", request)
    notificar_evento_documento(documento, "envio_revisao")

    messages.success(request, "Documento enviado para revisão.")
    return redirect("documentos:detalhes_documento", documento_id=documento.id)


@login_required
def aprovar_documento(request, documento_id):
    documento = get_object_or_404(Documento, id=documento_id)

    documento.status_documento = "Aprovado"
    documento.save(update_fields=["status_documento"])

    registrar_workflow(documento, "Aprovação Técnica – Coordenador", "Aprovado", request)
    notificar_evento_documento(documento, "aprovacao")

    messages.success(request, "Documento aprovado.")
    return redirect("documentos:detalhes_documento", documento_id=documento.id)


@login_required
def emitir_documento(request, documento_id):
    documento = get_object_or_404(Documento, id=documento_id)

    documento.status_emissao = "Emitido"
    documento.data_emissao_grdt = date.today()
    documento.save(update_fields=["status_emissao", "data_emissao_grdt"])

    registrar_workflow(documento, "Emissão Final", "Emitido", request)
    notificar_evento_documento(documento, "emissao")

    messages.success(request, "Documento emitido.")
    return redirect("documentos:detalhes_documento", documento_id=documento.id)


@login_required
def cancelar_documento(request, documento_id):
    documento = get_object_or_404(Documento, id=documento_id)

    documento.status_documento = "Cancelado"
    documento.status_emissao = "Cancelado"
    documento.save(update_fields=["status_documento", "status_emissao"])

    registrar_workflow(documento, "Emissão Final", "Cancelado", request)
    notificar_evento_documento(documento, "cancelamento")

    messages.success(request, "Documento cancelado.")
    return redirect("documentos:detalhes_documento", documento_id=documento.id)


# =================================================================
# GERAR DIFF ENTRE DUAS REVISÕES
# =================================================================

@login_required
def gerar_diff(request, documento_id, revA, revB):
    documento = get_object_or_404(Documento, id=documento_id)

    versao_a = get_object_or_404(
        DocumentoVersao, documento=documento, numero_revisao=revA
    )
    versao_b = get_object_or_404(
        DocumentoVersao, documento=documento, numero_revisao=revB
    )

    def ler_arquivo_texto(file_field):
        try:
            path = file_field.path
        except Exception:
            return None
        try:
            with open(path, "r", encoding="utf-8", errors="ignore") as f:
                return f.read().splitlines()
        except Exception:
            return None

    linhas_a = ler_arquivo_texto(versao_a.arquivo)
    linhas_b = ler_arquivo_texto(versao_b.arquivo)

    diff_text = []
    if linhas_a is not None and linhas_b is not None:
        diff_text = list(
            unified_diff(
                linhas_a,
                linhas_b,
                fromfile=f"Rev {revA}",
                tofile=f"Rev {revB}",
                lineterm="",
            )
        )

    return render(
        request,
        "documentos/diff.html",
        {
            "documento": documento,
            "versao_a": versao_a,
            "versao_b": versao_b,
            "diff": diff_text,
        },
    )


# =================================================================
# IMPORTAÇÃO LDP (SIMPLIFICADA)
# =================================================================

@login_required
def importar_ldp(request):
    if request.method == "POST":
        arquivo = request.FILES.get("arquivo")
        if not arquivo:
            messages.error(request, "Selecione um arquivo CSV ou XLSX.")
            return redirect("documentos:importar_ldp")

        nome = arquivo.name.lower()
        total_linhas = 0

        # Aqui está uma implementação segura e genérica.
        # Você pode adaptar o mapeamento de colunas depois.
        try:
            if nome.endswith(".csv"):
                decoded = arquivo.read().decode("utf-8", errors="ignore").splitlines()
                reader = csv.reader(decoded, delimiter=";")
                for row in reader:
                    total_linhas += 1
                    # TODO: mapear colunas → Documento
            elif nome.endswith(".xlsx"):
                wb = openpyxl.load_workbook(arquivo)
                ws = wb.active
                for _ in ws.iter_rows(min_row=2):  # pula cabeçalho
                    total_linhas += 1
                    # TODO: mapear colunas → Documento
            else:
                messages.error(request, "Formato não suportado. Use CSV ou XLSX.")
                return redirect("documentos:importar_ldp")
        except Exception as e:
            messages.error(request, f"Erro ao processar arquivo: {e}")
            return redirect("documentos:importar_ldp")

        messages.success(
            request,
            f"Arquivo processado com sucesso ({total_linhas} linhas lidas). Ajuste a lógica de importação conforme necessário.",
        )
        return redirect("documentos:listar_documentos")

    return render(request, "documentos/importar_ldp.html")


# =================================================================
# MEDIÇÃO / EXPORTAÇÃO MEDIÇÃO
# =================================================================

def _calcular_medicao_queryset(docs_qs):
    med_raw = docs_qs.values("tipo_doc").annotate(
        total=Count("id"),
        emitidos=Count("id", filter=Q(status_emissao="Emitido")),
        nr=Count("id", filter=Q(status_emissao="Não Recebido")),
    )

    linhas = []
    total_usd = 0
    total_brl = 0

    for m in med_raw:
        tipo = m["tipo_doc"] or "Sem Tipo"
        emit = m["emitidos"]
        nr = m["nr"]

        v_emit_usd = emit * VALOR_MEDICAO_USD
        v_nr_usd = nr * VALOR_MEDICAO_USD
        v_emit_brl = v_emit_usd * TAXA_CAMBIO_REAIS
        v_nr_brl = v_nr_usd * TAXA_CAMBIO_REAIS

        total_usd += v_emit_usd + v_nr_usd
        total_brl += v_emit_brl + v_nr_brl

        linhas.append(
            {
                "tipo_doc": tipo,
                "total": m["total"],
                "emitidos": emit,
                "nao_recebidos": nr,
                "valor_emitidos_usd": f"{v_emit_usd:,.2f}",
                "valor_nr_usd": f"{v_nr_usd:,.2f}",
                "valor_emitidos_brl": f"{v_emit_brl:,.2f}",
                "valor_nr_brl": f"{v_nr_brl:,.2f}",
            }
        )

    totais = {
        "total_docs": sum(m["total"] for m in med_raw),
        "total_usd": f"{total_usd:,.2f}",
        "total_brl": f"{total_brl:,.2f}",
    }

    return linhas, totais


@login_required
def medicao(request):
    docs = Documento.objects.filter(ativo=True)

    projeto = request.GET.get("projeto") or ""
    if projeto:
        docs = docs.filter(projeto__nome__icontains=projeto)

    linhas, totais = _calcular_medicao_queryset(docs)

    base_qs = Documento.objects.filter(ativo=True).select_related("projeto")

    return render(
        request,
        "documentos/medicao.html",
        {
            "linhas": linhas,
            "totais": totais,
            "projetos": base_qs.values_list("projeto__nome", flat=True).distinct(),
            "projeto_selecionado": projeto,
        },
    )


@login_required
def exportar_medicao_excel(request):
    docs = Documento.objects.filter(ativo=True)

    projeto = request.GET.get("projeto") or ""
    if projeto:
        docs = docs.filter(projeto__nome__icontains=projeto)

    linhas, totais = _calcular_medicao_queryset(docs)

    wb = openpyxl.Workbook()
    ws = wb.active
    ws.title = "Medição GED"

    headers = [
        "Tipo de Documento",
        "Total",
        "Emitidos",
        "Não Recebidos",
        "Valor Emitidos (USD)",
        "Valor Não Recebidos (USD)",
        "Valor Emitidos (BRL)",
        "Valor Não Recebidos (BRL)",
    ]
    ws.append(headers)

    header_fill = PatternFill(start_color="0052A2", end_color="0052A2", fill_type="solid")
    border = Border(
        left=Side(style="thin"),
        right=Side(style="thin"),
        top=Side(style="thin"),
        bottom=Side(style="thin"),
    )

    for col in ws[1]:
        col.fill = header_fill
        col.font = Font(color="FFFFFF", bold=True)
        col.border = border
        col.alignment = Alignment(horizontal="center")

    for linha in linhas:
        ws.append(
            [
                linha["tipo_doc"],
                linha["total"],
                linha["emitidos"],
                linha["nao_recebidos"],
                linha["valor_emitidos_usd"],
                linha["valor_nr_usd"],
                linha["valor_emitidos_brl"],
                linha["valor_nr_brl"],
            ]
        )

    row_total = [
        "TOTAL",
        totais["total_docs"],
        "",
        "",
        totais["total_usd"],
        "",
        totais["total_brl"],
        "",
    ]
    ws.append([])
    ws.append(row_total)

    for column_cells in ws.columns:
        length = max(len(str(cell.value)) if cell.value else 0 for cell in column_cells)
        ws.column_dimensions[column_cells[0].column_letter].width = length + 3

    output = BytesIO()
    wb.save(output)
    output.seek(0)

    filename = f"medicao_{date.today().isoformat()}.xlsx"

    return HttpResponse(
        output.getvalue(),
        content_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


# =================================================================
# EXCLUSÃO / LIXEIRA
# =================================================================

@login_required
def excluir_documento(request, documento_id):
    documento = get_object_or_404(Documento, id=documento_id)
    motivo = request.POST.get("motivo", "") if request.method == "POST" else ""
    mover_para_lixeira(documento, request, motivo=motivo)
    messages.success(request, "Documento movido para a lixeira.")
    return redirect("documentos:listar_documentos")


@login_required
def excluir_selecionados(request):
    if request.method != "POST":
        return redirect("documentos:listar_documentos")

    ids = request.POST.getlist("selecionados") or []
    count = 0
    for _id in ids:
        try:
            doc = Documento.objects.get(id=_id)
            if mover_para_lixeira(doc, request, motivo="Exclusão em lote"):
                count += 1
        except Documento.DoesNotExist:
            continue

    messages.success(request, f"{count} documento(s) movido(s) para a lixeira.")
    return redirect("documentos:listar_documentos")


@login_required
def lixeira(request):
    docs = Documento.objects.filter(ativo=False).order_by("-deletado_em")
    return render(request, "documentos/lixeira.html", {"documentos": docs})


@login_required
def restaurar_documento(request, documento_id):
    documento = get_object_or_404(Documento, id=documento_id)
    restaurar_da_lixeira(documento, request)
    messages.success(request, "Documento restaurado com sucesso.")
    return redirect("documentos:lixeira")


# =================================================================
# CONFIGURAÇÕES UNIFICADAS (Usuário + Administração)
# =================================================================

@login_required
def configuracoes(request):
    from apps.contas.models import UserConfig  # Importa aqui para evitar ciclos

    # Carrega ou cria configuração do usuário
    config, _ = UserConfig.objects.get_or_create(user=request.user)

    # Salvar preferências pessoais
    if request.method == "POST" and "salvar_prefs" in request.POST:
        config.tema = request.POST.get("tema", config.tema)
        config.animacoes = request.POST.get("animacoes", "True") == "True"
        config.notificacoes_email = request.POST.get("notificacoes_email", "True") == "True"
        config.dashboard_expandido = request.POST.get("dashboard_expandido", "True") == "True"
        config.save()
        messages.success(request, "Preferências atualizadas com sucesso!")

    # Dados para parte administrativa (apenas admins/master)
    projetos = Projeto.objects.all().order_by("nome")
    resp_disc = ResponsavelDisciplina.objects.all().order_by("disciplina")
    etapas = WorkflowEtapa.objects.all().order_by("ordem")

    return render(
        request,
        "documentos/configuracoes.html",
        {
            "projetos": projetos,
            "responsaveis": resp_disc,
            "etapas": etapas,
            "config": config,
        },
    )

# =================================================================
# BUSCA GLOBAL
# =================================================================

@login_required
def buscar_global(request):
    termo = request.GET.get("q", "").strip()
    resultados = []

    if termo:
        qs = Documento.objects.filter(ativo=True).select_related("projeto")
        qs = qs.filter(
            Q(codigo__icontains=termo)
            | Q(titulo__icontains=termo)
            | Q(disciplina__icontains=termo)
            | Q(projeto__nome__icontains=termo)
        )

        for doc in qs:
            resultados.append(
                {
                    "id": doc.id,
                    "codigo": highlight_text(doc.codigo, termo),
                    "titulo": highlight_text(doc.titulo, termo),
                    "disciplina": doc.disciplina or "",
                    "projeto": doc.projeto.nome if doc.projeto else "",
                }
            )

    return render(
        request,
        "documentos/buscar.html",
        {"resultados": resultados, "termo": termo},
    )

# =============================================
# 📊 DASHBOARD MASTER – FINANCE + STATUS ENGINE
# =============================================
from django.db.models import Count, Sum
from .models import Documento, LogAuditoria, ProjetoFinanceiro


def dashboard_master(request):
    projeto_nome = "TP25 NAVIOS HANDY CLASSE 80"
    taxa_brl = 5.7642

    # ============================
    # BASE DE DOCUMENTOS FILTRADOS
    # ============================
    docs = Documento.objects.filter(
        projeto__nome__icontains=projeto_nome,
        ativo=True
    )

    total_docs = docs.count()

    total_emitidos     = docs.filter(status_emissao="Emitido").count()
    total_aprovados    = docs.filter(status_emissao="Aprovado").count()
    total_em_revisao   = docs.filter(status_documento__icontains="Revisão").count()
    total_nao_recebidos = docs.filter(status_emissao="Não Recebido").count()
    total_excluidos    = docs.filter(deletado_em__isnull=False).count()
    total_restaurados  = docs.filter(motivo_exclusao__icontains="Restaurado").count()

    # ============================
    # FINANCEIRO POR FASE / STATUS
    # ============================
    valores = ProjetoFinanceiro.objects.filter(projeto__nome=projeto_nome)

    valor_basico   = valores.filter(fase="Básico").aggregate(total=Sum("valor_total_usd"))["total"] or 0
    valor_aprovado = valores.filter(fase="Aprovado").aggregate(total=Sum("valor_total_usd"))["total"] or 0
    valor_asbuilt  = valores.filter(fase="As Built").aggregate(total=Sum("valor_total_usd"))["total"] or 0


    total_basico_docs = docs.filter(fase="Básico").count() or 1

    # USD Unitários (valor / documentos)
    usd_basico_unit   = valor_basico   / total_basico_docs
    usd_aprovado_unit = valor_aprovado / total_basico_docs
    usd_asbuilt_unit  = valor_asbuilt  / total_basico_docs

    # Medição baseada no STATUS EMISSÃO
    valor_emitidos_usd = total_emitidos     * usd_basico_unit
    valor_nao_rec_usd  = total_nao_recebidos * usd_basico_unit
    valor_total_usd    = valor_emitidos_usd + valor_nao_rec_usd

    # Conversão BRL
    valor_emitidos_brl = valor_emitidos_usd * taxa_brl
    valor_nao_rec_brl  = valor_nao_rec_usd  * taxa_brl
    valor_total_brl    = valor_total_usd    * taxa_brl

    # =============
    # AUDITORIA
    # =============
    auditoria_acoes = LogAuditoria.objects.order_by('-data')[:10]

    top_excluidores = LogAuditoria.objects.filter(acao="Excluído") \
        .values('usuario') \
        .annotate(qtd=Count('id')) \
        .order_by('-qtd')[:5]

    # =====================
    # GRÁFICOS
    # =====================
    disc_labels = list(docs.values_list("disciplina", flat=True).distinct())
    disc_data   = [docs.filter(disciplina=d).count() for d in disc_labels]

    status_labels = ["Emitido", "Aprovado", "Revisão", "Não Recebido"]
    status_data   = [
        total_emitidos,
        total_aprovados,
        total_em_revisao,
        total_nao_recebidos
    ]

    # =====================
    # RENDERIZA O TEMPLATE
    # =====================
    context = {
        "total_docs": total_docs,
        "total_emitidos": total_emitidos,
        "total_aprovados": total_aprovados,
        "total_em_revisao": total_em_revisao,
        "total_nao_recebidos": total_nao_recebidos,
        "total_excluidos": total_excluidos,
        "total_restaurados": total_restaurados,

        "valor_emitidos_usd": valor_emitidos_usd,
        "valor_nao_rec_usd": valor_nao_rec_usd,
        "valor_total_usd": valor_total_usd,

        "valor_emitidos_brl": valor_emitidos_brl,
        "valor_nao_rec_brl": valor_nao_rec_brl,
        "valor_total_brl": valor_total_brl,

        # Graphs
        "disc_labels": disc_labels,
        "disc_data": disc_data,
        "status_labels": status_labels,
        "status_data": status_data,

        # Auditoria
        "top_excluidores": top_excluidores,
        "auditoria_acoes": auditoria_acoes,
    }

    return render(request, "documentos/dashboard_master.html", context)

# =================================================================
# BUSCA AJAX
# =================================================================

@login_required
def buscar_ajax(request):
    termo = request.GET.get("q", "").strip()
    items = []

    if termo:
        qs = Documento.objects.filter(ativo=True)
        qs = qs.filter(
            Q(codigo__icontains=termo)
            | Q(titulo__icontains=termo)
            | Q(disciplina__icontains=termo)
        )[:20]

        for d in qs:
            items.append(
                {
                    "id": d.id,
                    "codigo": d.codigo,
                    "titulo": d.titulo,
                    "disciplina": d.disciplina or "",
                }
            )

    return JsonResponse({"results": items})