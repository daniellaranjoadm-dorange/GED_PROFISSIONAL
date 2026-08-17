from django.urls import path

from . import views

app_name = "carimbos"

urlpatterns = [
    path("", views.criar_copia_controlada, name="criar"),
    path("guias/", views.guias_emissao, name="guias"),
    path("guias/processar/", views.processar_guia_emissao, name="processar_guia"),
    path("rastreabilidade/", views.rastreabilidade, name="rastreabilidade"),
    path("rastreabilidade/exportar/", views.exportar_rastreabilidade, name="exportar_rastreabilidade"),
    path(
        "rastreabilidade/<int:pk>/entregar/",
        views.confirmar_entrega,
        name="confirmar_entrega",
    ),
    path(
        "rastreabilidade/<int:pk>/recolher/",
        views.confirmar_recolhimento,
        name="confirmar_recolhimento",
    ),
]
