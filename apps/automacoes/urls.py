from django.urls import path

from apps.automacoes import views

app_name = "automacoes"

urlpatterns = [
    path("", views.painel, name="painel"),

    # Operations Center
    path(
        "ops-center/",
        views.ops_center,
        name="ops_center",
    ),

    path(
        "ops-center/runtime/",
        views.ops_center_runtime_partial,
        name="ops_center_runtime_partial",
    ),

    path(
        "ops-center/events/",
        views.ops_center_events_partial,
        name="ops_center_events_partial",
    ),

    # Legacy dashboard compatibility routes
    path(
        "dashboard-search/",
        views.ops_center,
        name="dashboard_search",
    ),

    path(
        "dashboard-jobs/",
        views.ops_center,
        name="dashboard_jobs",
    ),

    path(
        "dashboard-scheduler/",
        views.ops_center,
        name="dashboard_scheduler",
    ),

    # Automacoes principais
    path(
        "executar-atualizar-ld/",
        views.executar_atualizar_ld,
        name="atualizar_ld",
    ),

    path(
        "timeline-pcfs/",
        views.timeline_pcfs_view,
        name="timeline_pcfs",
    ),

    path(
        "transmittal-km/",
        views.executar_transmittal_km,
        name="transmittal_km",
    ),

    path(
        "grd-ghenova/",
        views.executar_grd_ghenova,
        name="grd_ghenova",
    ),

    path(
        "indexar-km/",
        views.executar_indice_km,
        name="indexar_km",
    ),

    path(
        "logs/",
        views.logs_automacoes,
        name="logs_automacoes",
    ),
]