# 1) Adicione import em apps/automacoes/views.py
from apps.automacoes.services.scheduler_monitor import obter_scheduler_monitoring


# 2) Cole a view:
@login_required
def dashboard_scheduler(request):
    contexto = obter_scheduler_monitoring()

    return render(
        request,
        "automacoes/dashboard_scheduler.html",
        contexto,
    )
