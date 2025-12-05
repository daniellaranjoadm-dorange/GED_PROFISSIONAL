from django.contrib import admin
from .models import Documento, ProjetoFinanceiro  # ⬅ importante

@admin.register(Documento)
class DocumentoAdmin(admin.ModelAdmin):
    list_display = ("codigo", "titulo", "revisao", "status_emissao", "projeto", "fase", "disciplina", "criado_em")
    search_fields = ("codigo", "titulo", "disciplina", "projeto__nome")
    list_filter = ("status_emissao", "fase", "projeto", "disciplina")

@admin.register(ProjetoFinanceiro)
class ProjetoFinanceiroAdmin(admin.ModelAdmin):
    list_display = ("projeto", "fase", "valor_total_usd")
    search_fields = ("projeto__nome", "fase")
    list_filter = ("fase", "projeto")
