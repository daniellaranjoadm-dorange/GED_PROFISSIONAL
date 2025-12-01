from django.contrib import admin
from django.http import HttpResponse
import csv

from .models import AuditoriaSolicitacao, SolicitarAcesso


# ============================================================
# ADMIN - AUDITORIA
# ============================================================

@admin.register(AuditoriaSolicitacao)
class AuditoriaSolicitacaoAdmin(admin.ModelAdmin):
    list_display = (
        "id",
        "solicitacao_id",
        "status_anterior",
        "status_novo",
        "usuario_responsavel",
        "usuario_criado",
        "ip",
        "data_registro",
    )

    list_filter = (
        "status_anterior",
        "status_novo",
        "usuario_responsavel",
        "usuario_criado",
        "data_registro",
    )

    search_fields = (
        "solicitacao__nome",
        "solicitacao__email",
        "observacao",
        "ip",
    )

    readonly_fields = (
        "solicitacao",
        "usuario_responsavel",
        "usuario_criado",
        "status_anterior",
        "status_novo",
        "ip",
        "observacao",
        "data_registro",
    )

    ordering = ("-data_registro",)

    actions = ["exportar_csv"]

    def exportar_csv(self, request, queryset):
        response = HttpResponse(content_type="text/csv")
        response["Content-Disposition"] = (
            'attachment; filename="auditoria_solicitacoes.csv"'
        )

        writer = csv.writer(response)
        writer.writerow([
            "ID",
            "Solicitação",
            "Status Anterior",
            "Status Novo",
            "Responsável",
            "Usuário Criado",
            "IP",
            "Observação",
            "Data Registro",
        ])

        for obj in queryset:
            writer.writerow([
                obj.id,
                obj.solicitacao_id,
                obj.status_anterior,
                obj.status_novo,
                str(obj.usuario_responsavel) if obj.usuario_responsavel else "",
                str(obj.usuario_criado) if obj.usuario_criado else "",
                obj.ip,
                obj.observacao,
                obj.data_registro,
            ])

        return response

    exportar_csv.short_description = "Exportar registros selecionados para CSV"


# ============================================================
# ADMIN - SOLICITAÇÕES DE ACESSO
# ============================================================

@admin.register(SolicitarAcesso)
class SolicitarAcessoAdmin(admin.ModelAdmin):
    list_display = (
        "nome",
        "email",
        "setor",
        "status",
        "data_solicitacao",
        "data_decisao",
    )

    list_filter = (
        "status",
        "setor",
        "data_solicitacao",
        "data_decisao",
    )

    search_fields = (
        "nome",
        "email",
        "setor",
    )

    readonly_fields = (
        "data_solicitacao",
        "data_decisao",
    )

    ordering = ("-data_solicitacao",)
