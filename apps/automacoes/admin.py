from django.contrib import admin

from apps.automacoes.models import AutomationExecutionLock, DocumentoLD, ExecucaoAutomacao, PCFTimeline, TransmittalKM, VinculoDoxManual


@admin.register(ExecucaoAutomacao)
class ExecucaoAutomacaoAdmin(admin.ModelAdmin):
    list_display = (
        "nome",
        "status",
        "sucesso",
        "usuario",
        "origem",
        "arquivo_origem",
        "ip_origem",
        "quantidade_processada",
        "duracao_segundos",
        "iniciado_em",
        "finalizado_em",
    )
    list_filter = ("status", "sucesso", "nome", "iniciado_em")
    search_fields = ("nome", "mensagem", "usuario__username", "usuario__first_name", "usuario__last_name")
    readonly_fields = (
        "nome",
        "usuario",
        "status",
        "sucesso",
        "mensagem",
        "detalhes",
        "origem",
        "arquivo_origem",
        "ip_origem",
        "quantidade_processada",
        "duracao_segundos",
        "iniciado_em",
        "finalizado_em",
    )
    ordering = ("-iniciado_em",)


@admin.register(AutomationExecutionLock)
class AutomationExecutionLockAdmin(admin.ModelAdmin):
    list_display = ("nome", "usuario", "adquirido_em", "expira_em")
    search_fields = ("nome", "usuario__username")
    readonly_fields = ("nome", "token", "usuario", "adquirido_em", "expira_em")


@admin.register(TransmittalKM)
class TransmittalKMAdmin(admin.ModelAdmin):
    list_display = ("documento", "transmittal_numero", "emissao", "status_parse", "criado_em")
    search_fields = ("documento", "titulo", "transmittal_numero", "pasta")
    list_filter = ("status_parse", "emissao", "criado_em")


@admin.register(PCFTimeline)
class PCFTimelineAdmin(admin.ModelAdmin):
    list_display = ("numero_documento", "numero_pcf", "tipo", "revisao_pcf", "open_comments", "status_final")
    search_fields = ("numero_documento", "numero_pcf", "titulo", "pcf_link")
    list_filter = ("tipo", "status_final")


@admin.register(VinculoDoxManual)
class VinculoDoxManualAdmin(admin.ModelAdmin):
    list_display = ("tipo", "identificador", "revisao", "ativo", "atualizado_em", "criado_por")
    search_fields = ("identificador", "chave_normalizada", "url_dox")
    list_filter = ("tipo", "ativo")
    readonly_fields = ("chave_normalizada", "criado_em", "atualizado_em")


@admin.register(DocumentoLD)
class DocumentoLDAdmin(admin.ModelAdmin):
    list_display = ("documento", "revisao", "disciplina", "status_documento", "status_grd", "status_final_pcf")
    search_fields = ("documento", "titulo", "disciplina", "grd", "pcf")
    list_filter = ("origem_aba", "disciplina", "status_documento", "status_grd", "status_final_pcf")
