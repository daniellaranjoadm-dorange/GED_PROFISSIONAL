from django.urls import path
from apps.automacoes import views

app_name = "automacoes"

urlpatterns = [
    path("", views.painel, name="painel"),

    # Operations Center
    path("ops-center/", views.ops_center, name="ops_center"),
    path("ops-center/runtime/", views.ops_center_runtime_partial, name="ops_center_runtime_partial"),
    path("ops-center/events/", views.ops_center_events_partial, name="ops_center_events_partial"),
    path("ops-center/live/", views.ops_center_live_partial, name="ops_center_live_partial"),

    # Legacy compatibility routes
    path("dashboard-search/", views.busca_global, name="dashboard_search"),
    path("dashboard-jobs/", views.logs_automacoes, name="dashboard_jobs"),
    path("dashboard-scheduler/", views.ops_center, name="dashboard_scheduler"),
    path("dashboard-pcfs/", views.dashboard_pcfs, name="dashboard_pcfs"),
    path("dashboard-km/", views.listar_transmittals_km, name="dashboard_km"),
    path("dashboard-grd/", views.logs_automacoes, name="dashboard_grd"),
    path("dashboard-ld/", views.dashboard_ld, name="dashboard_ld"),
    path("excecoes-documentais/", views.dashboard_excecoes_documentais, name="dashboard_excecoes_documentais"),
    path(
        "alertas-operacionais/",
        views.dashboard_alertas_operacionais,
        name="dashboard_alertas_operacionais",
    ),

    path(
        "executar-sync-km-ld/",
        views.executar_sync_km_ld,
        name="executar_sync_km_ld",
    ),

    path("dashboard-transmittals/", views.dashboard_transmittals, name="dashboard_transmittals"),
    path("dashboard-km-ld/", views.dashboard_km_ld, name="dashboard_km_ld"),
    path("importar-lista-km/", views.importar_lista_km, name="importar_lista_km"),

    # Legacy entity routes
    path("pcfs-timeline/", views.listar_pcfs_timeline, name="pcfs_timeline"),
    path("transmittals-km/", views.listar_transmittals_km, name="transmittals_km"),
    path("lista-ld/", views.listar_ld, name="lista_ld"),

    # Automações principais
    path("executar-atualizar-ld/", views.executar_atualizar_ld, name="atualizar_ld"),
    path("timeline-pcfs/", views.timeline_pcfs_view, name="timeline_pcfs"),
    path("transmittal-km/", views.executar_transmittal_km, name="transmittal_km"),
    path("grd-ghenova/", views.executar_grd_ghenova, name="grd_ghenova"),
    path("indexar-km/", views.executar_indice_km, name="indexar_km"),
    path("logs/", views.logs_automacoes, name="logs_automacoes"),

    # Runtime APIs
    path("api/runtime/health/", views.runtime_health_api, name="runtime_health_api"),
    path("api/runtime/metrics/", views.runtime_metrics_api, name="runtime_metrics_api"),
    path("api/runtime/events/", views.runtime_events_api, name="runtime_events_api"),
    path(
        "api/runtime/retention/dry-run/",
        views.runtime_retention_dry_run_api,
        name="runtime_retention_dry_run_api",
    ),
    path("busca-global/", views.busca_global, name="busca_global"),
    path("transmittals-km/<int:pk>/pdf/", views.abrir_pdf_transmittal_km, name="abrir_pdf_transmittal_km"),
    path("transmittals-km/<int:pk>/abrir-documento/", views.abrir_documento_transmittal_km, name="abrir_documento_transmittal_km"),
    path("transmittals-km/<int:pk>/abrir-pasta/", views.abrir_pasta_documento_transmittal_km, name="abrir_pasta_documento_transmittal_km"),
    path("ld/", views.listar_ld, name="listar_ld"),
    path("pcfs/", views.listar_pcfs_timeline, name="listar_pcfs_timeline"),
    path("pcfs/exportar-excel/", views.exportar_pcfs_timeline_excel, name="exportar_pcfs_timeline_excel"),
    path("ld/exportar-excel/", views.exportar_ld_excel, name="exportar_ld_excel"),
    path("pcfs/abrir/<int:pk>/", views.abrir_arquivo_pcf, name="abrir_arquivo_pcf"),
    path("ld/<int:pk>/<str:tipo>/abrir/", views.abrir_arquivo_ld, name="abrir_arquivo_ld"),
]
