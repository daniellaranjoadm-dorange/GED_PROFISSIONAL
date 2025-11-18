from django.urls import path
from . import views

app_name = "documentos"

urlpatterns = [

    # ============================
    # LOGIN / LOGOUT
    # ============================
    path("login/", views.login_view, name="login"),
    path("logout/", views.logout_view, name="logout"),

    # ============================
    # HOME / LISTAGEM
    # ============================
    path("", views.listar_documentos, name="home"),
    path("documentos/", views.listar_documentos, name="listar_documentos"),
    path("upload/", views.upload_documento, name="upload_documento"),

    # ============================
    # DETALHES / EDIÇÃO
    # ============================
    path("documento/<int:documento_id>/", views.detalhes_documento, name="detalhes_documento"),
    path("editar/<int:documento_id>/", views.editar_documento, name="editar_documento"),

    # ============================
    # REVISÕES
    # ============================
    path("nova-revisao/<int:documento_id>/", views.nova_revisao, name="nova_revisao"),
    path("historico/<str:codigo>/", views.historico, name="historico"),

    # ============================
    # ANEXOS (NOVO MÓDULO)
    # ============================
    path("documento/<int:documento_id>/arquivos/", views.adicionar_arquivos, name="adicionar_arquivos"),
    path("arquivo/<int:arquivo_id>/excluir/", views.excluir_arquivo, name="excluir_arquivo"),

    # ============================
    # WORKFLOW
    # ============================
    path("enviar-revisao/<int:documento_id>/", views.enviar_para_revisao, name="enviar_para_revisao"),
    path("aprovar/<int:documento_id>/", views.aprovar_documento, name="aprovar_documento"),
    path("emitir/<int:documento_id>/", views.emitir_documento, name="emitir_documento"),
    path("cancelar/<int:documento_id>/", views.cancelar_documento, name="cancelar_documento"),

    # ============================
    # IMPORTAÇÃO LDP
    # ============================
    path("importar-ldp/", views.importar_ldp, name="importar_ldp"),

    # ============================
    # DASHBOARDS
    # ============================
    path("dashboard/", views.dashboard, name="dashboard"),
    path("dashboard-enterprise/", views.dashboard_enterprise, name="dashboard_enterprise"),

    # ============================
    # MEDIÇÃO
    # ============================
    path("medicao/", views.medicao, name="medicao"),
    path("medicao/exportar/", views.exportar_medicao_excel, name="exportar_medicao_excel"),

    # ============================
    # EXCLUSÃO / LIXEIRA
    # ============================
    path("excluir/<int:documento_id>/", views.excluir_documento, name="excluir_documento"),
    path("excluir-selecionados/", views.excluir_selecionados, name="excluir_selecionados"),

    path("lixeira/", views.lixeira, name="lixeira"),
    path("restaurar/<int:documento_id>/", views.restaurar_documento, name="restaurar_documento"),
]
