from django.urls import path
from . import views


app_name = "documentos"

urlpatterns = [
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
    # NOVA VERSÃO
    # ============================
    path("documento/<int:documento_id>/nova-versao/", views.nova_versao, name="nova_versao"),

    # ============================
    # ANEXOS
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
    path("documento/<int:documento_id>/enviar-proxima-etapa/", views.enviar_proxima_etapa, name="enviar_proxima_etapa"),
    path("retornar-etapa/<int:documento_id>/", views.retornar_etapa, name="retornar_etapa"),
    path("gerar-diff/<int:documento_id>/<str:revA>/<str:revB>/", views.gerar_diff, name="gerar_diff"),

    # ============================
    # IMPORTAÇÃO LDP
    # ============================
    path("importar-ldp/", views.importar_ldp, name="importar_ldp"),

    # ============================
    # DASHBOARDS
    # ============================
    path("dashboard/", views.dashboard, name="dashboard"),
    path("dashboard-enterprise/", views.dashboard_enterprise, name="dashboard_enterprise"),
    path("painel-workflow/", views.painel_workflow, name="painel_workflow"),
    path("painel-workflow/exportar/", views.painel_workflow_exportar_excel, name="painel_workflow_exportar"),
    path("dashboard-master/", views.dashboard_master, name="dashboard_master"),

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
    path("lixeira/esvaziar/", views.esvaziar_lixeira, name="esvaziar_lixeira"),
    path("restaurar/<int:documento_id>/", views.restaurar_documento, name="restaurar_documento"),

    # ============================
    # CONFIGURAÇÕES
    # ============================
    path("configuracoes/", views.configuracoes, name="configuracoes"),

    # ============================
    # BUSCA GLOBAL
    # ============================
    path("buscar/", views.buscar_global, name="buscar_global"),

    # ============================
    # AJAX — SUGESTÕES
    # ============================
    path("buscar-ajax/", views.buscar_ajax, name="buscar_ajax"),
]