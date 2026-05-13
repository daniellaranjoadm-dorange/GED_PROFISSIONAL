# 1) Adicione este import no topo do apps/automacoes/views.py:
from apps.automacoes.services.job_analytics import obter_job_analytics


# 2) Cole esta view no final do apps/automacoes/views.py:
@login_required
def dashboard_jobs(request):
    contexto = obter_job_analytics()
    return render(
        request,
        "automacoes/dashboard_jobs.html",
        contexto,
    )
