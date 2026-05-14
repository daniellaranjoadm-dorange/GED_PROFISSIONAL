from django.contrib.auth.decorators import login_required
from django.shortcuts import render

from apps.automacoes.services.ops_center_service import OperationsCenterService
from apps.automacoes.services.runtime_events import RuntimeEventStreamService


@login_required
def ops_center_runtime_partial(request):
    return render(
        request,
        "automacoes/partials/_ops_runtime_observability.html",
        {
            "ops": OperationsCenterService.build_dashboard(),
            "runtime_events": RuntimeEventStreamService.build_stream(limit=20),
            "runtime_events_summary": RuntimeEventStreamService.summary(),
        },
    )


@login_required
def ops_center_events_partial(request):
    return render(
        request,
        "automacoes/partials/_ops_runtime_events.html",
        {
            "runtime_events": RuntimeEventStreamService.build_stream(limit=30),
            "runtime_events_summary": RuntimeEventStreamService.summary(),
        },
    )
