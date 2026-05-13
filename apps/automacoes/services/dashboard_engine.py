"""
Engine de composição dos dashboards enterprise.

Este módulo transforma KPIs já calculados em estruturas reutilizáveis
por views, APIs, relatórios e BI futuro.

Regra de arquitetura:
- dashboard_metrics calcula números
- dashboard_engine monta contexto/estrutura de apresentação
- views apenas recebem request e renderizam templates
"""

from apps.automacoes.services.dashboard_metrics import obter_kpis_dashboard


def _valor(kpis, chave, padrao=0):
    """Lê um KPI de forma segura, preservando fallback previsível."""
    valor = kpis.get(chave, padrao)
    return padrao if valor is None else valor


def montar_automacoes_dashboard(kpis, health_map=None):
    """
    Monta os cards principais do painel de automações.

    Mantém a estrutura compatível com o template atual do painel.
    """
    health_map = health_map or {}

    automacoes = [
        {
            "nome": "Atualização LD",
            "subtitulo": "Lista de Documentos",
            "icone": "bi-file-earmark-spreadsheet",
            "badge": "Crítica",
            "badge_class": "auto-badge-warning",
            "descricao": "Sincroniza dados documentais, revisões, PCFs, GRDs, links de rede e medição.",
            "form_url": "automacoes:atualizar_ld",
            "botao": "Executar Atualização LD",
            "botao_class": "btn-primary",
            "dashboard_url": "automacoes:dashboard_ld",
            "registros_url": "automacoes:lista_ld",
            "metricas": [
                {"label": "Linhas LD", "valor": _valor(kpis, "total_ld")},
                {"label": "Com PCF", "valor": _valor(kpis, "total_ld_com_pcf")},
                {"label": "Sem PCF", "valor": _valor(kpis, "total_ld_sem_pcf")},
            ],
        },
        {
            "nome": "Timeline PCFs",
            "subtitulo": "Comentários e revisões",
            "icone": "bi-bar-chart-line",
            "badge": "Integrada",
            "badge_class": "auto-badge-success",
            "descricao": "Gera e atualiza a timeline das PCFs recebidas e respondidas.",
            "form_url": "automacoes:timeline_pcfs",
            "botao": "Gerar Timeline PCFs",
            "botao_class": "btn-success",
            "dashboard_url": "automacoes:dashboard_pcfs",
            "registros_url": "automacoes:pcfs_timeline",
            "metricas": [
                {"label": "PCFs", "valor": _valor(kpis, "total_pcfs")},
                {"label": "Open", "valor": _valor(kpis, "total_pcfs_open")},
                {"label": "Not Released", "valor": _valor(kpis, "total_pcfs_not_released")},
            ],
        },
        {
            "nome": "Transmittal KM",
            "subtitulo": "Parser PDF",
            "icone": "bi-box-seam",
            "badge": "Parser PDF",
            "badge_class": "auto-badge-info",
            "descricao": "Lê PDFs KM e consolida transmittals para acompanhamento documental.",
            "form_url": "automacoes:transmittal_km",
            "botao": "Consolidar Transmittals KM",
            "botao_class": "btn-info",
            "dashboard_url": "automacoes:dashboard_transmittals",
            "registros_url": "automacoes:transmittals_km",
            "metricas": [
                {"label": "Registros", "valor": _valor(kpis, "total_transmittals")},
                {"label": "Transmittals", "valor": _valor(kpis, "total_transmittals_unicos")},
                {"label": "Sem PDF", "valor": _valor(kpis, "total_transmittals_sem_pdf")},
            ],
        },
        {
            "nome": "Índice KM",
            "subtitulo": "Arquivos e documentos KM",
            "icone": "bi-hdd-network",
            "badge": "Indexação",
            "badge_class": "auto-badge-info",
            "descricao": "Varre a pasta Documentos KM, indexa arquivos técnicos e acelera a abertura direta dos documentos.",
            "form_url": "automacoes:indexar_km",
            "botao": "Atualizar Índice KM",
            "botao_class": "btn-primary",
            "dashboard_url": "automacoes:transmittals_km",
            "registros_url": "automacoes:transmittals_km",
            "metricas": [
                {"label": "Arquivos", "valor": _valor(kpis, "total_km_index")},
                {"label": "Docs técnicos", "valor": _valor(kpis, "total_km_docs_index")},
                {"label": "Letters", "valor": _valor(kpis, "total_km_transmittals_index")},
            ],
        },
        {
            "nome": "GRD GHENOVA",
            "subtitulo": "Consolidação GRDs 7K e 14K",
            "icone": "bi-diagram-3",
            "badge": "Engenharia",
            "badge_class": "auto-badge-neutral",
            "descricao": "Processa PDFs de GRD e gera planilhas consolidadas por empreendimento.",
            "form_url": "automacoes:grd_ghenova",
            "botao": "Consolidar GRDs GHENOVA",
            "botao_class": "btn-secondary",
            "dashboard_url": "",
            "registros_url": "",
            "metricas": [
                {"label": "Fonte", "valor": "PDF"},
                {"label": "Escopo", "valor": "7K/14K"},
                {"label": "Status", "valor": "Ativo"},
            ],
        },
    ]

    for rotina in automacoes:
        rotina["health"] = health_map.get(rotina["nome"], {})

    return automacoes


def obter_contexto_dashboard_base(health_map=None):
    """
    Retorna KPIs e cards principais do painel enterprise.

    Esta função ainda não substitui a view inteira; ela prepara o próximo
    patch incremental onde o painel passará a consumir a engine.
    """
    kpis = obter_kpis_dashboard()
    return {
        **kpis,
        "automacoes": montar_automacoes_dashboard(kpis, health_map=health_map),
    }
