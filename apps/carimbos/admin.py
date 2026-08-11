from django.contrib import admin

from .models import DistribuicaoCopia, GuiaEmissao


@admin.register(GuiaEmissao)
class GuiaEmissaoAdmin(admin.ModelAdmin):
    list_display = ("numero", "data_emissao", "remetente", "processada_por")
    search_fields = ("numero", "remetente", "email_remetente")
    list_filter = ("data_emissao",)


@admin.register(DistribuicaoCopia)
class DistribuicaoCopiaAdmin(admin.ModelAdmin):
    list_display = (
        "documento",
        "revisao",
        "guia",
        "destinatario",
        "status",
        "emitida_em",
    )
    search_fields = (
        "documento",
        "guia__numero",
        "destinatario",
        "email_destinatario",
    )
    list_filter = ("status", "revisao", "emitida_em")
