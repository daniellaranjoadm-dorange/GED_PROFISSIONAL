from django.contrib.auth.decorators import login_required
from django.shortcuts import render

from apps.automacoes.services.ops_center_service import OperationsCenterService


@login_required
def ops_center_runtime_partial(request):
    """
    Partial read-only endpoint for near-realtime runtime observability.
    Designed for HTMX/polling without running scheduler actions.
    """
    ops = OperationsCenterService.build_dashboard()
    return render(
        request,
        "automacoes/partials/_ops_runtime_observability.html",
        {"ops": ops},
    )
