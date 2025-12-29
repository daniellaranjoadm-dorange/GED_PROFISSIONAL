# ==============================================
# DASHBOARD MASTER – GED ENTERPRISE NAVAL
# ==============================================

from __future__ import annotations

import json
import logging

from django.contrib.admin.views.decorators import staff_member_required
from django.core.exceptions import FieldError
from django.db.models import Count, Sum, F
from django.shortcuts import render, redirect

from apps.documentos.models import Documento, ProjetoFinanceiro, LogAuditoria

logger = logging.getLogger(__name__)

TAXA = 5.7642


def money_br(v) -> str:
    v = float(v if v else 0)
    return f"{v:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")


def _safe_sum(qs, field_name: str) -> float:
    """
    Soma um campo com segurança.
    Se o campo não existir no model, retorna 0 e loga warning (sem quebrar).
    """
    try:
        return float(qs.aggregate(total=Sum(field_name))["total"] or 0)
    except FieldError:
        logger.warning("Campo '%s' não existe em Documento. Usando 0.", field_name)
        return 0.0
    except Exception:
        logger.exception("Falha ao somar campo '%s'. Usando 0.", field_name)
        return 0.0


def _norm_label(value: str | None, default: str) -> str:
    v = (value or "").strip()
    return v if v else default


@staff_member_required
def dashboard(request):
    # Base (para combos e contagens globais)
    docs_base = Documento.objects.filter(ativo=True, deletado_em__isnull=True)

    # filtros (aplicados em docs)
    projeto_filtro = (request.GET.get("projeto") or "").strip()
    disciplina_filtro = (request.GET.get("disciplina") or "").strip()
    status_ldp_filtro = (request.GET.get("status_ldp") or "").strip()
    status_emissao_filtro = (request.GET.get("status_emissao") or "").strip()

    docs = docs_base
    if projeto_filtro:
        docs = docs.filter(projeto__nome__icontains=projeto_filtro)
    if disciplina_filtro:
        docs = docs.filter(disciplina__icontains=disciplina_filtro)
    if status_ldp_filtro:
        docs = docs.filter(status_documento__icontains=status_ldp_filtro)
    if status_emissao_filtro:
        docs = docs.filter(status_emissao__icontains=status_emissao_filtro)

    ha_filtros = any([projeto_filtro, disciplina_filtro, status_ldp_filtro, status_emissao_filtro])

    # KPI
    total_docs = docs.count()
    total_aprovados = docs.filter(status_documento__icontains="aprov").count()
    total_em_revisao = docs.filter(status_documento__icontains="revis").count()
    total_emitidos = docs.filter(status_emissao__icontains="emit").count()
    total_nao_recebidos = docs.filter(status_emissao__icontains="pend").count()

    # “Excluídos” aqui é global (fora do filtro) — mantido assim
    total_excluidos = Documento.objects.filter(deletado_em__isnull=False).count()

    # “Restaurados”: tenta via auditoria (mais correto). Se não houver, fallback 0.
    try:
        total_restaurados = LogAuditoria.objects.filter(acao__icontains="Restaurad").count()
    except Exception:
        logger.exception("Falha ao calcular total_restaurados via LogAuditoria")
        total_restaurados = 0

    # Financeiro por documento (se existir campo; se não, não quebra)
    v_emitidos_usd = _safe_sum(docs.filter(status_emissao__icontains="emit"), "valor_usd")
    v_nao_rec_usd = _safe_sum(docs.filter(status_emissao__icontains="pend"), "valor_usd")
    v_total_usd = _safe_sum(docs, "valor_usd")

    v_emitidos_brl = _safe_sum(docs.filter(status_emissao__icontains="emit"), "valor_brl")
    v_nao_rec_brl = _safe_sum(docs.filter(status_emissao__icontains="pend"), "valor_brl")
    v_total_brl = _safe_sum(docs, "valor_brl")

    # Financeiro projetos (ProjetoFinanceiro) — já existia
    proj = ProjetoFinanceiro.objects.select_related("projeto")
    fin_usd, fin_brl = {}, {}
    for p in proj:
        nome = p.projeto.nome if p.projeto else "Sem Projeto"
        usd = float(p.valor_total_usd or 0)
        brl = usd * TAXA
        fin_usd[nome] = fin_usd.get(nome, 0) + usd
        fin_brl[nome] = fin_brl.get(nome, 0) + brl

    total_fin_usd = sum(fin_usd.values())
    total_fin_brl = sum(fin_brl.values())

    fin_labels = json.dumps(list(fin_usd.keys()), ensure_ascii=False)
    fin_data = json.dumps(list(fin_usd.values()))

    # Gráficos
    disc_query = docs.values("disciplina").annotate(total=Count("id")).order_by("-total")
    disc_labels = json.dumps(
        [_norm_label(i["disciplina"], "Sem Disciplina") for i in disc_query],
        ensure_ascii=False,
    )
    disc_data = json.dumps([i["total"] for i in disc_query])

    status_query = docs.values("status_documento").annotate(total=Count("id"))
    status_labels = json.dumps(
        [_norm_label(i["status_documento"], "Sem Status") for i in status_query],
        ensure_ascii=False,
    )
    status_data = json.dumps([i["total"] for i in status_query])

    # Auditoria (top excluidores usando deletado_por do Documento)
    top_excluidores = (
        Documento.objects.filter(deletado_em__isnull=False)
        .values(usuario=F("deletado_por"))
        .annotate(qtd=Count("id"))
        .order_by("-qtd")[:5]
    )
    auditoria_acoes = LogAuditoria.objects.order_by("-data")[:10]

    # Combos (sempre da base, para não “sumirem”)
    projetos_combo = (
        docs_base.values_list("projeto__nome", flat=True)
        .exclude(projeto__nome__isnull=True)
        .exclude(projeto__nome__exact="")
        .distinct()
        .order_by("projeto__nome")
    )
    disciplinas_combo = (
        docs_base.values_list("disciplina", flat=True)
        .exclude(disciplina__isnull=True)
        .exclude(disciplina__exact="")
        .distinct()
        .order_by("disciplina")
    )
    status_ldp_combo = (
        docs_base.values_list("status_documento", flat=True)
        .exclude(status_documento__isnull=True)
        .exclude(status_documento__exact="")
        .distinct()
        .order_by("status_documento")
    )
    status_emissao_combo = (
        docs_base.values_list("status_emissao", flat=True)
        .exclude(status_emissao__isnull=True)
        .exclude(status_emissao__exact="")
        .distinct()
        .order_by("status_emissao")
    )

    context = {
        "total_docs": total_docs,
        "total_aprovados": total_aprovados,
        "total_em_revisao": total_em_revisao,
        "total_emitidos": total_emitidos,
        "total_nao_recebidos": total_nao_recebidos,
        "total_excluidos": total_excluidos,
        "total_restaurados": total_restaurados,
        "v_emitidos_usd": money_br(v_emitidos_usd),
        "v_nao_rec_usd": money_br(v_nao_rec_usd),
        "v_total_usd": money_br(v_total_usd),
        "v_emitidos_brl": money_br(v_emitidos_brl),
        "v_nao_rec_brl": money_br(v_nao_rec_brl),
        "v_total_brl": money_br(v_total_brl),
        "total_fin_usd": money_br(total_fin_usd),
        "total_fin_brl": money_br(total_fin_brl),
        "fin_labels": fin_labels,
        "fin_data": fin_data,
        "disc_labels": disc_labels,
        "disc_data": disc_data,
        "status_labels": status_labels,
        "status_data": status_data,
        "top_excluidores": top_excluidores,
        "auditoria_acoes": auditoria_acoes,
        "projetos": projetos_combo,
        "disciplinas": disciplinas_combo,
        "status_ldp_list": status_ldp_combo,
        "status_emissao_list": status_emissao_combo,
        "ha_filtros": ha_filtros,
        "filtros": {
            "projeto": projeto_filtro,
            "disciplina": disciplina_filtro,
            "status_ldp": status_ldp_filtro,
            "status_emissao": status_emissao_filtro,
        },
    }

    return render(request, "documentos/dashboard_master.html", context)


@staff_member_required
def solicitacoes(request):
    """
    Sidebar bate em /dashboard/solicitacoes/.
    Se o módulo real estiver em /contas/... usamos redirect com namespace.
    """
    return redirect("contas:painel_solicitacoes")


@staff_member_required
def usuarios_permissoes(request):
    """
    Página ponte para "Usuários e Permissões".
    Mantém robustez usando o admin do Django.
    """
    return redirect("/admin/auth/user/")
