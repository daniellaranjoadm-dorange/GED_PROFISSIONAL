from datetime import timedelta

from django.db.models import Avg, Count, Sum
from django.db.models.functions import TruncDate
from django.utils import timezone

from apps.automacoes.models import SearchAudit


def _periodo_inicio(dias):
    try:
        dias = int(dias)
    except (TypeError, ValueError):
        dias = 30

    dias = max(1, min(dias, 365))
    return timezone.now() - timedelta(days=dias), dias


def obter_search_analytics(dias=30, limite=10):
    """
    Consolida métricas executivas das buscas globais do GED.

    Mantém a view leve e deixa a regra de analytics em service testável.
    """
    inicio, dias = _periodo_inicio(dias)
    limite = max(1, min(int(limite or 10), 50))

    qs = SearchAudit.objects.filter(criado_em__gte=inicio)

    total_buscas = qs.count()
    buscas_sem_resultado = qs.filter(total_geral=0).count()
    buscas_com_erro = qs.filter(sucesso=False).count()
    buscas_com_resultado = max(total_buscas - buscas_sem_resultado, 0)

    taxa_sucesso_resultado = (
        round((buscas_com_resultado / total_buscas) * 100, 1)
        if total_buscas
        else 0
    )

    duracao_media_ms = qs.aggregate(media=Avg("duracao_ms")).get("media") or 0

    top_termos = list(
        qs.exclude(termo="")
        .values("termo")
        .annotate(
            total=Count("id"),
            media_resultados=Avg("total_geral"),
            ultima_busca=MaxDate("criado_em"),
        )
        .order_by("-total", "termo")[:limite]
    )

    sem_resultado = list(
        qs.filter(total_geral=0)
        .exclude(termo="")
        .values("termo")
        .annotate(total=Count("id"), ultima_busca=MaxDate("criado_em"))
        .order_by("-total", "termo")[:limite]
    )

    por_tipo = list(
        qs.values("tipo")
        .annotate(total=Count("id"))
        .order_by("-total", "tipo")
    )

    por_origem = list(
        qs.values("origem")
        .annotate(total=Count("id"))
        .order_by("-total", "origem")
    )

    por_dia = list(
        qs.annotate(dia=TruncDate("criado_em"))
        .values("dia")
        .annotate(total=Count("id"))
        .order_by("dia")
    )

    usuarios_ativos = list(
        qs.exclude(usuario__isnull=True)
        .values("usuario__username")
        .annotate(total=Count("id"))
        .order_by("-total", "usuario__username")[:limite]
    )

    totalizadores_destino = qs.aggregate(
        total_km=Sum("total_km"),
        total_transmittals=Sum("total_transmittals"),
        total_ld=Sum("total_ld"),
        total_pcfs=Sum("total_pcfs"),
    )

    destino_totais = {
        "km": totalizadores_destino.get("total_km") or 0,
        "transmittals": totalizadores_destino.get("total_transmittals") or 0,
        "ld": totalizadores_destino.get("total_ld") or 0,
        "pcfs": totalizadores_destino.get("total_pcfs") or 0,
    }

    return {
        "periodo_dias": dias,
        "total_buscas": total_buscas,
        "buscas_sem_resultado": buscas_sem_resultado,
        "buscas_com_erro": buscas_com_erro,
        "buscas_com_resultado": buscas_com_resultado,
        "taxa_sucesso_resultado": taxa_sucesso_resultado,
        "duracao_media_ms": round(float(duracao_media_ms), 1) if duracao_media_ms else 0,
        "top_termos": top_termos,
        "sem_resultado": sem_resultado,
        "por_tipo": por_tipo,
        "por_origem": por_origem,
        "por_dia": por_dia,
        "usuarios_ativos": usuarios_ativos,
        "destino_totais": destino_totais,
        "destino_labels": ["KM", "Transmittals", "LD", "PCFs"],
        "destino_values": [
            destino_totais["km"],
            destino_totais["transmittals"],
            destino_totais["ld"],
            destino_totais["pcfs"],
        ],
        "dia_labels": [
            item["dia"].strftime("%d/%m") if item.get("dia") else ""
            for item in por_dia
        ],
        "dia_values": [item.get("total") or 0 for item in por_dia],
    }


def MaxDate(campo):
    """
    Wrapper pequeno para manter import local claro nos agrupamentos.
    """
    from django.db.models import Max

    return Max(campo)
