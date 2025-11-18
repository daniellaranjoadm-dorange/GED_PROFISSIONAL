from django.db import models
from datetime import datetime
import os


# ======================================================================
# 📄 MODELO PRINCIPAL — DOCUMENTO
# ======================================================================
class Documento(models.Model):
    projeto = models.CharField(max_length=100, blank=True, null=True)
    fase = models.CharField(max_length=50, blank=True, null=True)
    tipo_doc = models.CharField(max_length=100, blank=True, null=True)

    codigo = models.CharField(max_length=200)
    revisao = models.CharField(max_length=10, default='0')

    disciplina = models.CharField(max_length=50, blank=True, null=True)
    titulo = models.CharField(max_length=255)

    status_ldp = models.CharField(max_length=50, blank=True, null=True)
    status_emissao = models.CharField(max_length=50, blank=True, null=True)

    numero_grdt = models.CharField(max_length=50, blank=True, null=True)
    numero_pcf = models.CharField(max_length=50, blank=True, null=True)
    data_emissao_tp = models.DateField(blank=True, null=True)

    criado_em = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.codigo} - Rev {self.revisao}"


# ======================================================================
# 📎 ARQUIVOS DO DOCUMENTO — VERSÃO SIMPLIFICADA
# ======================================================================
class ArquivoDocumento(models.Model):
    documento = models.ForeignKey(
        Documento,
        on_delete=models.CASCADE,
        related_name="arquivos"
    )

    arquivo = models.FileField(upload_to="documentos/anexos/")
    nome_original = models.CharField(max_length=255, blank=True, null=True)

    tipo = models.CharField(max_length=20, blank=True, null=True)
    enviado_em = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"Anexo {self.nome_original} → {self.documento.codigo}"

    @property
    def extensao(self):
        try:
            return self.arquivo.name.split(".")[-1].lower()
        except:
            return ""

# ======================================================================
# 👤 RESPONSÁVEIS POR DISCIPLINA
# ======================================================================
class ResponsavelDisciplina(models.Model):
    disciplina = models.CharField(max_length=50, unique=True)
    responsavel = models.CharField(max_length=200)
    email = models.CharField(max_length=200, blank=True, null=True)

    def __str__(self):
        return f"{self.disciplina} - {self.responsavel}"


# ======================================================================
# 🔧 WORKFLOW DO DOCUMENTO
# ======================================================================
class WorkflowDocumento(models.Model):
    documento = models.ForeignKey(
        Documento,
        on_delete=models.CASCADE,
        related_name="workflow"
    )
    etapa = models.CharField(max_length=100)
    status = models.CharField(max_length=50)

    usuario = models.CharField(max_length=200)
    data = models.DateTimeField(auto_now_add=True)

    observacao = models.TextField(blank=True, null=True)

    def __str__(self):
        return f"{self.documento.codigo} - {self.etapa} ({self.status})"


# ======================================================================
# 📥 HISTÓRICO DE IMPORTAÇÕES
# ======================================================================
class ImportacaoLDP(models.Model):
    criado_em = models.DateTimeField(auto_now_add=True)

    arquivo_nome = models.CharField(max_length=255)
    total_sucesso = models.IntegerField(default=0)
    total_erros = models.IntegerField(default=0)

    log = models.TextField(blank=True)

    def __str__(self):
        return f"Importação {self.id} - {self.arquivo_nome} ({self.criado_em.strftime('%d/%m/%Y %H:%M')})"
