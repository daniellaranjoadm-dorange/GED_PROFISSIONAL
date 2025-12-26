from django.contrib.admin.views.decorators import staff_member_required
from django.db.models import Count, Avg, DurationField, ExpressionWrapper, F
from django.db.models.functions import TruncMonth
from django.shortcuts import render
from django.utils import timezone

import json

from backend.apps.apps.solicitacoes.models import SolicitarAcesso, AuditoriaSolicitacao
from backend.apps.apps.documentos.models import Documento, DocumentoVersao, DocumentoWorkflowStatus


@staff_member_required
def dashboard_index(request):
    # ================================
    # KPIs principais
    # ================================
    total = SolicitarAcesso.objects.count()
    pendentes = SolicitarAcesso.objects.filter(
        status=SolicitarAcesso.STATUS_PENDENTE
    ).count()
    aprovadas = SolicitarAcesso.objects.filter(
        status=SolicitarAcesso.STATUS_APROVADO
    ).count()
    negadas = SolicitarAcesso.objects.filter(
        status=SolicitarAcesso.STATUS_NEGADO
    ).count()

    # Taxa de aprovação (%)
    taxa_aprovacao = (aprovadas / total * 100) if total > 0 else 0

    # Tempo médio de decisão (em horas)
    diff_expr = ExpressionWrapper(
        F("data_decisao") - F("data_solicitacao"),
        output_field=DurationField(),
    )
    avg_decisao = (
        SolicitarAcesso.objects
        .filter(data_decisao__isnull=False)
        .aggregate(media=Avg(diff_expr))
        .get("media")
    )
    tempo_medio_decisao_horas = (
        round(avg_decisao.total_seconds() / 3600, 1)
        if avg_decisao
        else None
    )

    # Usuários criados automaticamente (via aprovação)
    usuarios_criados_auto = AuditoriaSolicitacao.objects.filter(
        usuario_criado__isnull=False,
        status_novo=SolicitarAcesso.STATUS_APROVADO,
    ).count()

    # ================================
    # Gráfico: Solicitações por status
    # ================================
    status_map = dict(SolicitarAcesso.STATUS_CHOICES)
    qs_status = (
        SolicitarAcesso.objects.values("status")
        .annotate(total=Count("id"))
        .order_by("status")
    )
    chart_status_labels = [
        status_map.get(item["status"], item["status"])
        for item in qs_status
    ]
    chart_status_data = [item["total"] for item in qs_status]

    # ================================
    # Gráfico: Solicitações por mês
    # ================================
    qs_mes = (
        SolicitarAcesso.objects
        .annotate(mes=TruncMonth("data_solicitacao"))
        .values("mes")
        .annotate(total=Count("id"))
        .order_by("mes")
    )
    chart_mes_labels = [
        item["mes"].strftime("%m/%Y") if item["mes"] else "N/A"
        for item in qs_mes
    ]
    chart_mes_data = [item["total"] for item in qs_mes]

    # ================================
    # Gráfico: Solicitações por setor
    # ================================
    qs_setor = (
        SolicitarAcesso.objects
        .values("setor")
        .annotate(total=Count("id"))
        .order_by("setor")
    )
    chart_setor_labels = [
        item["setor"] or "Não informado"
        for item in qs_setor
    ]
    chart_setor_data = [item["total"] for item in qs_setor]

    # ================================
    # Listas recentes
    # ================================
    ultimas_solicitacoes = (
        SolicitarAcesso.objects
        .order_by("-data_solicitacao")[:10]
    )
    ultimas_auditorias = (
        AuditoriaSolicitacao.objects
        .select_related("solicitacao", "usuario_responsavel", "usuario_criado")
        .order_by("-data_registro")[:10]
    )

    # ================================
    # 📊 BLOCO NOVO – DASHBOARD DE DOCUMENTOS
    # ================================
    docs_qs = Documento.objects.filter(ativo=True, deletado_em__isnull=True)

    doc_total = docs_qs.count()
    doc_em_revisao = docs_qs.filter(status_emissao="Em Revisão").count()
    doc_aprovados = docs_qs.filter(status_emissao="Aprovado").count()
    doc_emitidos = docs_qs.filter(status_emissao="Emitido").count()
    doc_cancelados = docs_qs.filter(status_emissao="Cancelado").count()

    docs_por_disciplina = docs_qs.values("disciplina").annotate(total=Count("id")).order_by("-total")[:10]
    chart_docs_disciplina_labels = [d["disciplina"] or "—" for d in docs_por_disciplina]
    chart_docs_disciplina_data = [d["total"] for d in docs_por_disciplina]

    docs_por_status = docs_qs.values("status_emissao").annotate(total=Count("id")).order_by("-total")
    chart_docs_status_labels = [d["status_emissao"] or "—" for d in docs_por_status]
    chart_docs_status_data = [d["total"] for d in docs_por_status]

    docs_por_mes = docs_qs.filter(data_emissao_tp__isnull=False).annotate(mes=TruncMonth("data_emissao_tp")).values("mes").annotate(total=Count("id")).order_by("mes")
    chart_docs_mes_labels = [d["mes"].strftime("%m/%Y") for d in docs_por_mes if d["mes"]]
    chart_docs_mes_data = [d["total"] for d in docs_por_mes if d["mes"]]

    ultimos_docs = docs_qs.order_by(F("data_emissao_tp").desc(nulls_last=True), "-criado_em")[:25]

    ultimas_revisoes = DocumentoVersao.objects.select_related("documento").order_by("-criado_em")[:3]

    docs_atrasados = DocumentoWorkflowStatus.objects.select_related("documento", "etapa").filter(prazo_final__isnull=False, prazo_final__lt=timezone.now()).order_by("prazo_final")[:25]

    context = {
        # KPIs existente
        "kpi_total": total,
        "kpi_pendentes": pendentes,
        "kpi_aprovadas": aprovadas,
        "kpi_negadas": negadas,
        "kpi_taxa_aprovacao": round(taxa_aprovacao, 1),
        "kpi_tempo_medio_decisao_horas": tempo_medio_decisao_horas,
        "kpi_usuarios_criados_auto": usuarios_criados_auto,

        # Dados para gráficos existentes
        "chart_status_labels": json.dumps(chart_status_labels),
        "chart_status_data": json.dumps(chart_status_data),
        "chart_mes_labels": json.dumps(chart_mes_labels),
        "chart_mes_data": json.dumps(chart_mes_data),
        "chart_setor_labels": json.dumps(chart_setor_labels),
        "chart_setor_data": json.dumps(chart_setor_data),

        # Listas existentes
        "ultimas_solicitacoes": ultimas_solicitacoes,
        "ultimas_auditorias": ultimas_auditorias,
        "agora": timezone.now(),

        # 📄 KPIs de Documentos
        "doc_total": doc_total,
        "doc_em_revisao": doc_em_revisao,
        "doc_aprovados": doc_aprovados,
        "doc_emitidos": doc_emitidos,
        "doc_cancelados": doc_cancelados,

        # 📊 Gráficos Documentos
        "chart_docs_disciplina_labels": json.dumps(chart_docs_disciplina_labels),
        "chart_docs_disciplina_data": json.dumps(chart_docs_disciplina_data),
        "chart_docs_status_labels": json.dumps(chart_docs_status_labels),
        "chart_docs_status_data": json.dumps(chart_docs_status_data),
        "chart_docs_mes_labels": json.dumps(chart_docs_mes_labels),
        "chart_docs_mes_data": json.dumps(chart_docs_mes_data),

        # 📄 Listas Documentos
        "ultimos_docs": ultimos_docs,
        "ultimas_revisoes": ultimas_revisoes,
        "docs_atrasados": docs_atrasados,
    }

    return render(request, "dashboard/index.html", context)
