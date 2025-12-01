from django.contrib import admin
from .models import SolicitarAcesso


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
