from django.db import models
from django.conf import settings
from django.contrib.auth.models import Group

# ======================================================================
# 🏗 PROJETO — BASE MULTI-CONTRATO
# ======================================================================
class Projeto(models.Model):
    nome = models.CharField(max_length=120, unique=True)
    cliente = models.CharField(max_length=120, blank=True, null=True)

    pasta_base = models.CharField(
        max_length=500,
        help_text="Caminho base na rede onde serão criadas as pastas de saída (GRDT/GED)",
    )

    prefixo_ged = models.CharField(max_length=50, default="GED")
    ativo = models.BooleanField(default=True)
    criado_em = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = "Projeto"
        verbose_name_plural = "Projetos"

    def __str__(self):
        return self.nome


# ======================================================================
# 📄 DOCUMENTO CENTRAL DO GED
# ======================================================================
class Documento(models.Model):
    projeto = models.ForeignKey(Projeto, on_delete=models.CASCADE, related_name="documentos",
                                null=True, blank=True)

    fase = models.CharField(max_length=50, blank=True, null=True)

    tipo_doc = models.CharField("Tipo de Documento", max_length=100, null=True, blank=True)

    codigo = models.CharField(max_length=200)
    revisao = models.CharField(max_length=10, default="0")
    titulo = models.CharField(max_length=255)
    disciplina = models.CharField(max_length=50, blank=True, null=True)

    status_documento = models.CharField(max_length=50, blank=True, null=True)
    status_emissao = models.CharField(max_length=50, blank=True, null=True)

    grdt_cliente = models.CharField(max_length=50, blank=True, null=True)
    resposta_cliente = models.CharField(max_length=255, blank=True, null=True)

    data_emissao_grdt = models.DateField("Data Emissão GRDT", blank=True, null=True)

    # FINANCEIRO por documento (NAVEMÃE READY)
    valor_brl = models.DecimalField("Valor (R$)", max_digits=15, decimal_places=2,
                                    null=True, blank=True)
    valor_usd = models.DecimalField("Valor (USD)", max_digits=15, decimal_places=2,
                                    null=True, blank=True)

    # GED / Metadados
    ged_interna = models.CharField(max_length=50, blank=True, null=True)
    criado_em = models.DateTimeField(auto_now_add=True)
    ativo = models.BooleanField(default=True)

    deletado_em = models.DateTimeField(blank=True, null=True)
    deletado_por = models.CharField(max_length=200, blank=True, null=True)
    motivo_exclusao = models.CharField(max_length=255, blank=True, null=True)

    etapa_atual = models.CharField(max_length=100,
                                  default="Revisão Interna – Disciplina")

    class Meta:
        verbose_name = "Documento"
        verbose_name_plural = "Documentos"
        ordering = ["codigo", "revisao"]

    def __str__(self):
        return f"{self.codigo} - Rev {self.revisao}"


# ======================================================================
# ANEXOS
# ======================================================================
class ArquivoDocumento(models.Model):
    documento = models.ForeignKey(Documento, on_delete=models.CASCADE, related_name="arquivos")
    arquivo = models.FileField(upload_to="documentos/anexos/")
    nome_original = models.CharField(max_length=255, blank=True, null=True)
    tipo = models.CharField(max_length=20, blank=True, null=True)
    enviado_em = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-enviado_em"]

    def __str__(self):
        return f"Anexo {self.nome_original} → {self.documento.codigo}"

    @property
    def extensao(self):
        return self.arquivo.name.split(".")[-1].lower()


# ======================================================================
# CONTROLE DE VERSÕES
# ======================================================================
class DocumentoVersao(models.Model):
    documento = models.ForeignKey(Documento, on_delete=models.CASCADE, related_name="versoes")
    numero_revisao = models.CharField(max_length=10)
    arquivo = models.FileField(upload_to="documentos/versoes/")
    criado_em = models.DateTimeField(auto_now_add=True)
    criado_por = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL,
                                   null=True, blank=True)
    observacao = models.TextField(blank=True)
    status_revisao = models.CharField(
        max_length=20,
        choices=[
            ("RASCUNHO", "Rascunho"),
            ("REVISAO", "Em Revisão"),
            ("APROVADO", "Aprovado"),
            ("CANCELADO", "Cancelado"),
        ],
        default="REVISAO",
    )

    class Meta:
        ordering = ["-criado_em"]

    def __str__(self):
        return f"{self.documento.codigo} - Rev {self.numero_revisao}"


# ======================================================================
# RESPONSÁVEL POR DISCIPLINA
# ======================================================================
class ResponsavelDisciplina(models.Model):
    disciplina = models.CharField(max_length=50, unique=True)
    responsavel = models.CharField(max_length=200)
    email = models.CharField(max_length=200, blank=True, null=True)

    class Meta:
        ordering = ["disciplina"]

    def __str__(self):
        return f"{self.disciplina} - {self.responsavel}"


# ======================================================================
# WORKFLOW
# ======================================================================
class WorkflowEtapa(models.Model):
    nome = models.CharField(max_length=100)
    ordem = models.PositiveIntegerField()
    prazo_dias = models.PositiveIntegerField(default=0)
    grupos_responsaveis = models.ManyToManyField(Group, blank=True)

    ativa = models.BooleanField(default=True)

    class Meta:
        ordering = ["ordem"]

    def __str__(self):
        return f"{self.ordem} - {self.nome}"


class DocumentoWorkflowStatus(models.Model):
    documento = models.OneToOneField(Documento, on_delete=models.CASCADE, related_name="workflow_status")
    etapa = models.ForeignKey(WorkflowEtapa, on_delete=models.SET_NULL, null=True, blank=True)
    iniciado_em = models.DateTimeField(auto_now_add=True)
    prazo_final = models.DateTimeField(null=True, blank=True)

    @property
    def atrasado(self):
        from django.utils import timezone
        return self.prazo_final and timezone.now() > self.prazo_final

    def __str__(self):
        return f"{self.documento.codigo} → {self.etapa.nome if self.etapa else '(sem etapa)'}"


# ======================================================================
# LOG AUDITORIA
# ======================================================================
class LogAuditoria(models.Model):
    usuario = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL,
                                null=True, blank=True)
    documento = models.ForeignKey(Documento, on_delete=models.SET_NULL,
                                  null=True, blank=True, related_name="logs")
    acao = models.CharField(max_length=50)
    descricao = models.TextField(blank=True, null=True)
    data = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-data"]

    def __str__(self):
        user = self.usuario.username if self.usuario else "Sistema"
        doc = self.documento.codigo if self.documento else "Sem doc"
        return f"{self.acao} - {doc} - {user}"


def registrar_log(usuario, documento, acao, descricao=""):
    LogAuditoria.objects.create(
        usuario=usuario if usuario and getattr(usuario, "is_authenticated", False) else None,
        documento=documento,
        acao=acao,
        descricao=descricao
    )


# ======================================================================
# 🏦 FINANCEIRO MULTIPROJETO
# ======================================================================
class ProjetoFinanceiro(models.Model):
    projeto = models.ForeignKey(Projeto, on_delete=models.CASCADE, related_name="financeiro")
    fase = models.CharField(max_length=50)  # BASICO/APROVADO/ASBUILT
    valor_total_usd = models.DecimalField(max_digits=12, decimal_places=2)

    descricao = models.CharField(max_length=255, null=True, blank=True)
    moeda = models.CharField(max_length=10, default="USD")

    def __str__(self):
        return f"{self.projeto.nome} - {self.fase} - {self.valor_total_usd} USD"
