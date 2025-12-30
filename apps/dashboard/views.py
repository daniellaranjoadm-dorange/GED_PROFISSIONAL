# ==============================================
# DASHBOARD MASTER – GED ENTERPRISE NAVAL
# ==============================================

from django.contrib.admin.views.decorators import staff_member_required
from django.contrib.auth.models import User, Group
from django.db.models import Count, Sum, F
from django.shortcuts import render, redirect
import json
import logging

from apps.documentos.models import Documento, ProjetoFinanceiro, LogAuditoria

logger = logging.getLogger(__name__)

TAXA = 5.7642


def money_br(v):
    v = float(v if v else 0)
    return f"{v:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")


@staff_member_required
def dashboard(request):
    docs = Documento.objects.filter(ativo=True, deletado_em__isnull=True).select_related("projeto")

    # filtros
    projeto_filtro = (request.GET.get("projeto") or "").strip()
    disciplina_filtro = (request.GET.get("disciplina") or "").strip()
    status_ldp_filtro = (request.GET.get("status_ldp") or "").strip()
    status_emissao_filtro = (request.GET.get("status_emissao") or "").strip()

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

    total_excluidos = Documento.objects.filter(deletado_em__isnull=False).count()
    total_restaurados = Documento.objects.filter(deletado_em__isnull=False, ativo=True).count()

    # financeiro documentos USD/BRL (se existir campos no model)
    v_emitidos_usd = docs.filter(status_emissao__icontains="emit").aggregate(v=Sum("valor_usd"))["v"] or 0
    v_nao_rec_usd = docs.filter(status_emissao__icontains="pend").aggregate(v=Sum("valor_usd"))["v"] or 0
    v_total_usd = docs.aggregate(v=Sum("valor_usd"))["v"] or 0

    v_emitidos_brl = docs.filter(status_emissao__icontains="emit").aggregate(v=Sum("valor_brl"))["v"] or 0
    v_nao_rec_brl = docs.filter(status_emissao__icontains="pend").aggregate(v=Sum("valor_brl"))["v"] or 0
    v_total_brl = docs.aggregate(v=Sum("valor_brl"))["v"] or 0

    # financeiro projetos
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

    # gráficos (evita None)
    disc_query = (
        docs.exclude(disciplina__isnull=True)
        .exclude(disciplina__exact="")
        .values("disciplina")
        .annotate(total=Count("id"))
        .order_by("-total")
    )
    disc_labels = json.dumps([i["disciplina"] for i in disc_query], ensure_ascii=False)
    disc_data = json.dumps([i["total"] for i in disc_query])

    status_query = (
        docs.exclude(status_documento__isnull=True)
        .exclude(status_documento__exact="")
        .values("status_documento")
        .annotate(total=Count("id"))
    )
    status_labels = json.dumps([i["status_documento"] for i in status_query], ensure_ascii=False)
    status_data = json.dumps([i["total"] for i in status_query])

    # auditoria
    top_excluidores = (
        Documento.objects.filter(deletado_em__isnull=False)
        .values(usuario=F("deletado_por"))
        .annotate(qtd=Count("id"))
        .order_by("-qtd")[:5]
    )
    auditoria_acoes = LogAuditoria.objects.order_by("-data")[:10]

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
        "projetos": (
            docs.exclude(projeto__nome__isnull=True)
            .exclude(projeto__nome__exact="")
            .values_list("projeto__nome", flat=True).distinct().order_by("projeto__nome")
        ),
        "disciplinas": (
            docs.exclude(disciplina__isnull=True)
            .exclude(disciplina__exact="")
            .values_list("disciplina", flat=True).distinct().order_by("disciplina")
        ),
        "status_ldp_list": (
            docs.exclude(status_documento__isnull=True)
            .exclude(status_documento__exact="")
            .values_list("status_documento", flat=True).distinct().order_by("status_documento")
        ),
        "status_emissao_list": (
            docs.exclude(status_emissao__isnull=True)
            .exclude(status_emissao__exact="")
            .values_list("status_emissao", flat=True).distinct().order_by("status_emissao")
        ),
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
    Sidebar bate em /dashboard/solicitacoes/ mas o módulo real está em /contas/painel-solicitacoes/.
    Redirect seguro para eliminar 404.
    """
    return redirect("contas:painel_solicitacoes")


@staff_member_required
def usuarios_permissoes(request):
    """
    Lista todos os usuários com seus grupos e permissões.
    """
    usuarios = User.objects.all().select_related().prefetch_related("groups", "user_permissions")

    context = {
        "usuarios": usuarios
    }
    return render(request, "dashboard/usuarios_permissoes.html", context)
