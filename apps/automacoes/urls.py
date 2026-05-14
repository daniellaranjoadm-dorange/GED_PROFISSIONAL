from django.urls import path
from apps.automacoes import views

app_name = "automacoes"

urlpatterns = [
    path("", views.painel, name="painel"),

    path("ops-center/", views.ops_center, name="ops_center"),
    path("ops-center/runtime/", views.ops_center_runtime_partial, name="ops_center_runtime_partial"),
    path("ops-center/events/", views.ops_center_events_partial, name="ops_center_events_partial"),

    # Legacy compatibility routes
    path("dashboard-search/", views.ops_center, name="dashboard_search"),
    path("dashboard-jobs/", views.ops_center, name="dashboard_jobs"),
    path("dashboard-scheduler/", views.ops_center, name="dashboard_scheduler"),

    path("dashboard-pcfs/", views.timeline_pcfs_view, name="dashboard_pcfs"),
    path("dashboard-km/", views.executar_transmittal_km, name="dashboard_km"),
    path("dashboard-grd/", views.executar_grd_ghenova, name="dashboard_grd"),

    path("pcfs-timeline/", views.timeline_pcfs_view, name="pcfs_timeline"),
    path("transmittals-km/", views.listar_transmittals_km, name="transmittals_km"),
    path("lista-ld/", views.executar_atualizar_ld, name="lista_ld"),

    path("executar-atualizar-ld/", views.executar_atualizar_ld, name="atualizar_ld"),
    path("timeline-pcfs/", views.timeline_pcfs_view, name="timeline_pcfs"),
    path("transmittal-km/", views.executar_transmittal_km, name="transmittal_km"),
    path("grd-ghenova/", views.executar_grd_ghenova, name="grd_ghenova"),
    path("indexar-km/", views.executar_indice_km, name="indexar_km"),
    path("logs/", views.logs_automacoes, name="logs_automacoes"),
    path("dashboard-ld/",views.painel,name="dashboard_ld"),
    path("dashboard-transmittals/",views.painel,name="dashboard_transmittals",
),
]
