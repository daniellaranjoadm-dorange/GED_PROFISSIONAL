from django.db.models import Avg, Count

from apps.automacoes.models import JobExecution


def _formatar_ms(valor):
    if valor is None:
        return "0 ms"

    valor = int(valor or 0)

    if valor < 1000:
        return f"{valor} ms"

    segundos = valor / 1000

    if segundos < 60:
        return f"{segundos:.1f} s"

    minutos = int(segundos // 60)
    resto = int(segundos % 60)
    return f"{minutos} min {resto} s"


def obter_job_analytics(limit=30):
    """
    Consolida métricas operacionais dos jobs do GED.

    Mantém a lógica de agregação fora das views, permitindo reuso futuro em:
    - dashboard web
    - API
    - scheduler
    - health checks
    - relatórios executivos
    """

    jobs = JobExecution.objects.all()

    total = jobs.count()
    total_pending = jobs.filter(status=JobExecution.STATUS_PENDING).count()
    total_running = jobs.filter(status=JobExecution.STATUS_RUNNING).count()
    total_success = jobs.filter(status=JobExecution.STATUS_SUCCESS).count()
    total_failed = jobs.filter(status=JobExecution.STATUS_FAILED).count()

    finalizados = total_success + total_failed
    taxa_sucesso = round((total_success / finalizados) * 100, 1) if finalizados else 0

    duracao_media_ms = (
        jobs.exclude(duration_ms__isnull=True)
        .aggregate(media=Avg("duration_ms"))
        .get("media")
        or 0
    )
    duracao_media_ms = round(duracao_media_ms)

    por_status = list(
        jobs.values("status")
        .annotate(total=Count("id"))
        .order_by("-total", "status")
    )

    por_job = list(
        jobs.values("job_name")
        .annotate(total=Count("id"))
        .order_by("-total", "job_name")[:10]
    )

    recentes = jobs.select_related("created_by").order_by("-created_at")[:limit]

    ultimo_job = recentes[0] if recentes else None
    ultima_falha = (
        jobs.filter(status=JobExecution.STATUS_FAILED)
        .select_related("created_by")
        .order_by("-created_at")
        .first()
    )

    return {
        "total": total,
        "total_pending": total_pending,
        "total_running": total_running,
        "total_success": total_success,
        "total_failed": total_failed,
        "finalizados": finalizados,
        "taxa_sucesso": taxa_sucesso,
        "duracao_media_ms": duracao_media_ms,
        "duracao_media_fmt": _formatar_ms(duracao_media_ms),
        "por_status": por_status,
        "por_job": por_job,
        "recentes": recentes,
        "ultimo_job": ultimo_job,
        "ultima_falha": ultima_falha,
    }
