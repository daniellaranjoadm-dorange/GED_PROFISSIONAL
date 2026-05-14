from django.urls import path

from . import views

app_name = "automacoes"

urlpatterns = [
    path("", views.painel, name="painel"),
    path("atualizar-ld/", views.executar_atualizar_ld, name="atualizar_ld"),
    path("timeline-pcfs/", views.timeline_pcfs_view, name="timeline_pcfs"),
    path("transmittal-km/", views.executar_transmittal_km, name="transmittal_km"),
    path("grd-ghenova/", views.executar_grd_ghenova, name="grd_ghenova"),
    path("km-indexar/", views.executar_indice_km, name="indexar_km"),
    path("busca-global/", views.busca_global_ged, name="busca_global"),
    path("api/busca-global/", views.api_busca_global_ged, name="api_busca_global"),
    path("km-index/<int:pk>/abrir/", views.abrir_km_index, name="abrir_km_index"),
    path("km-index/<int:pk>/abrir-pasta/", views.abrir_pasta_km_index, name="abrir_pasta_km_index"),
    path("logs/", views.logs_automacoes, name="logs_automacoes"),

    path(
        "transmittals-km/",
        views.listar_transmittals_km,
        name="transmittals_km",
    ),
    path(
        "transmittals-km/<int:pk>/abrir-pdf/",
        views.abrir_pdf_transmittal_km,
        name="abrir_pdf_transmittal_km",
    ),

    path(
        "transmittals-km/<int:pk>/abrir-documento/",
        views.abrir_documento_transmittal_km,
        name="abrir_documento_transmittal_km",
    ),
    path(
        "transmittals-km/<int:pk>/abrir-pasta/",
        views.abrir_pasta_documento_transmittal_km,
        name="abrir_pasta_documento_transmittal_km",
    ),

    path(
        "pcfs/",
        views.listar_pcfs_timeline,
        name="pcfs_timeline",
    ),
    path(
        "pcfs/<int:pk>/abrir-arquivo/",
        views.abrir_arquivo_pcf,
        name="abrir_arquivo_pcf",
    ),
    path(
        "pcfs/exportar/",
        views.exportar_pcfs_timeline_excel,
        name="exportar_pcfs_timeline_excel",
    ),
    path(
        "dashboard-pcfs/",
        views.dashboard_pcfs,
        name="dashboard_pcfs",
    ),
    path(
        "ld/",
        views.listar_ld,
        name="lista_ld",
    ),
    path(
        "ld/exportar/",
        views.exportar_ld_excel,
        name="exportar_ld_excel",
    ),
    path(
        "dashboard-ld/",
        views.dashboard_ld,
        name="dashboard_ld",
    ),
    path(
        "dashboard-search/",
        views.dashboard_search,
        name="dashboard_search",
    ),
    path(
        "dashboard-transmittals/",
        views.dashboard_transmittals,
        name="dashboard_transmittals",
    ),
    path(
        "ld/<int:pk>/abrir/<str:tipo>/",
        views.abrir_arquivo_ld,
        name="abrir_arquivo_ld",
    ),

    path("ops-center/", views.ops_center, name="ops_center"),
    path("ops-center/partial/runtime/", views.ops_center_runtime_partial, name="ops_center_runtime_partial"),
    path("ops-center/partial/events/", views.ops_center_events_partial, name="ops_center_events_partial"),
    path("ops-center/partial/metrics/", views.ops_center_metrics_partial, name="ops_center_metrics_partial"),
