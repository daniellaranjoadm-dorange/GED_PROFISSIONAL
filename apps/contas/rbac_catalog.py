"""Catálogo central dos perfis e permissões operacionais do GED."""

ROLES_PADRAO = {
    "MASTER": "Administração completa do GED e das automações.",
    "GESTOR": "Visão gerencial, indicadores, dashboards, logs e relatórios.",
    "DOCUMENT_CONTROL": "Operação documental de LD, PCF, KM e rotinas de produção.",
    "ARQUIVO_TECNICO": "Cadastro, organização, consulta e distribuição controlada do acervo técnico.",
    "ENGENHEIRO": "Consulta técnica e manutenção de documentos de engenharia.",
    "REVISOR": "Revisão documental e consulta técnica.",
    "APROVADOR": "Aprovação, emissão e consulta documental.",
    "CONSULTA": "Acesso somente para leitura aos módulos operacionais.",
    "OPERADOR_AUTOMACOES": "Execução e acompanhamento das automações homologadas.",
}

PERMISSOES_POR_PAPEL = {
    "MASTER": ["sistema.dashboard_enterprise", "administracao.gerenciar", "ged.visualizar", "documento.criar", "documento.editar", "documento.excluir", "documento.revisar", "documento.aprovar", "documento.emitir", "copias.visualizar", "copias.operar", "ld_pcf.visualizar", "km.visualizar", "automacoes.visualizar", "automacoes.ver_logs", "automacoes.ver_ops_center", "automacoes.executar_ld_projeto_basico", "automacoes.executar_timeline_pcf", "automacoes.executar_transmittal_km", "automacoes.executar_indice_km", "automacoes.executar_sync_km_ld", "automacoes.executar_relatorio_km", "automacoes.executar_grd", "automacoes.executar_ld_legado"],
    "GESTOR": ["sistema.dashboard_enterprise", "ged.visualizar", "copias.visualizar", "ld_pcf.visualizar", "km.visualizar", "automacoes.visualizar", "automacoes.ver_logs", "automacoes.ver_ops_center", "automacoes.executar_relatorio_km"],
    "DOCUMENT_CONTROL": ["ged.visualizar", "documento.criar", "documento.editar", "documento.revisar", "documento.emitir", "copias.visualizar", "copias.operar", "ld_pcf.visualizar", "km.visualizar", "automacoes.visualizar", "automacoes.ver_logs", "automacoes.executar_ld_projeto_basico", "automacoes.executar_timeline_pcf", "automacoes.executar_transmittal_km", "automacoes.executar_indice_km", "automacoes.executar_sync_km_ld"],
    "ARQUIVO_TECNICO": ["ged.visualizar", "documento.criar", "documento.editar", "copias.visualizar", "copias.operar", "ld_pcf.visualizar", "km.visualizar"],
    "ENGENHEIRO": ["ged.visualizar", "documento.criar", "documento.editar", "ld_pcf.visualizar", "km.visualizar", "automacoes.visualizar"],
    "REVISOR": ["ged.visualizar", "documento.revisar", "ld_pcf.visualizar", "km.visualizar"],
    "APROVADOR": ["ged.visualizar", "documento.aprovar", "documento.emitir", "copias.visualizar", "ld_pcf.visualizar", "km.visualizar"],
    "CONSULTA": ["ged.visualizar", "copias.visualizar", "ld_pcf.visualizar", "km.visualizar", "automacoes.visualizar"],
    "OPERADOR_AUTOMACOES": ["ld_pcf.visualizar", "km.visualizar", "automacoes.visualizar", "automacoes.ver_logs", "automacoes.ver_ops_center", "automacoes.executar_ld_projeto_basico", "automacoes.executar_timeline_pcf", "automacoes.executar_transmittal_km", "automacoes.executar_indice_km", "automacoes.executar_sync_km_ld", "automacoes.executar_relatorio_km", "automacoes.executar_grd"],
}

PERFIS_OPERACIONAIS = tuple(nome for nome in ROLES_PADRAO if nome != "MASTER")
