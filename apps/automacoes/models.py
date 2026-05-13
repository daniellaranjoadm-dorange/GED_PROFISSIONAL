from django.conf import settings
from django.db import models


class ExecucaoAutomacao(models.Model):
    STATUS_INICIADO = "iniciado"
    STATUS_PROCESSANDO = "processando"
    STATUS_SUCESSO = "sucesso"
    STATUS_SUCESSO_PARCIAL = "sucesso_parcial"
    STATUS_ERRO = "erro"
    STATUS_CANCELADO = "cancelado"

    STATUS_CHOICES = [
        (STATUS_INICIADO, "Iniciado"),
        (STATUS_PROCESSANDO, "Processando"),
        (STATUS_SUCESSO, "Sucesso"),
        (STATUS_SUCESSO_PARCIAL, "Sucesso parcial"),
        (STATUS_ERRO, "Erro"),
        (STATUS_CANCELADO, "Cancelado"),
    ]

    nome = models.CharField(max_length=100)
    usuario = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="execucoes_automacoes",
    )
    status = models.CharField(
        max_length=30,
        choices=STATUS_CHOICES,
        default=STATUS_INICIADO,
        db_index=True,
    )
    sucesso = models.BooleanField(default=False, db_index=True)
    mensagem = models.TextField(blank=True)
    detalhes = models.JSONField(default=dict, blank=True)
    quantidade_processada = models.IntegerField(default=0)
    duracao_segundos = models.FloatField(default=0)
    iniciado_em = models.DateTimeField(auto_now_add=True, db_index=True)
    finalizado_em = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ["-iniciado_em"]
        verbose_name = "Execução de automação"
        verbose_name_plural = "Execuções de automações"

    def __str__(self):
        return f"{self.nome} - {self.status}"


class SearchAudit(models.Model):
    """Registro operacional das buscas executadas no GED."""

    ORIGEM_WEB = "web"
    ORIGEM_API = "api"
    ORIGEM_CHOICES = [
        (ORIGEM_WEB, "Web"),
        (ORIGEM_API, "API"),
    ]

    usuario = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="buscas_ged",
    )
    termo = models.CharField(max_length=500, db_index=True)
    tipo = models.CharField(max_length=50, blank=True, default="todos", db_index=True)
    origem = models.CharField(
        max_length=30,
        choices=ORIGEM_CHOICES,
        default=ORIGEM_WEB,
        db_index=True,
    )

    total_geral = models.PositiveIntegerField(default=0)
    total_km = models.PositiveIntegerField(default=0)
    total_transmittals = models.PositiveIntegerField(default=0)
    total_ld = models.PositiveIntegerField(default=0)
    total_pcfs = models.PositiveIntegerField(default=0)

    duracao_ms = models.PositiveIntegerField(default=0)
    sucesso = models.BooleanField(default=True, db_index=True)
    mensagem = models.TextField(blank=True)

    criado_em = models.DateTimeField(auto_now_add=True, db_index=True)

    class Meta:
        ordering = ["-criado_em"]
        verbose_name = "Auditoria de busca GED"
        verbose_name_plural = "Auditorias de busca GED"
        indexes = [
            models.Index(fields=["termo", "tipo"]),
            models.Index(fields=["origem", "criado_em"]),
            models.Index(fields=["sucesso", "criado_em"]),
        ]

    def __str__(self):
        return f"{self.termo} ({self.total_geral})"



class TransmittalKM(models.Model):
    documento = models.CharField(max_length=100, blank=True)
    titulo = models.TextField(blank=True)
    pasta = models.CharField(max_length=255, blank=True)
    emissao = models.CharField(max_length=100, blank=True)
    proposito_emissao = models.CharField(max_length=150, blank=True)
    data_envio = models.CharField(max_length=20, blank=True)
    transmittal_numero = models.CharField(max_length=100, blank=True)
    arquivo_pdf = models.TextField(blank=True)
    status_parse = models.CharField(max_length=50, blank=True)
    observacao_parse = models.TextField(blank=True)
    atualizado_em = models.DateTimeField(auto_now=True)
    criado_em = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = ("documento", "transmittal_numero")
        ordering = ["documento"]

    def __str__(self):
        return f"{self.documento} - {self.transmittal_numero}"


class KMFileIndex(models.Model):
    nome_arquivo = models.CharField(max_length=500)
    caminho_completo = models.TextField(unique=True)
    pasta = models.TextField(blank=True)

    extensao = models.CharField(max_length=20, blank=True, db_index=True)
    tamanho_bytes = models.BigIntegerField(default=0)
    modificado_em = models.DateTimeField(null=True, blank=True)

    nome_normalizado = models.CharField(max_length=600, blank=True, db_index=True)
    stem_normalizado = models.CharField(max_length=600, blank=True, db_index=True)
    documento_extraido = models.CharField(max_length=255, blank=True, db_index=True)

    eh_transmittal_letter = models.BooleanField(default=False, db_index=True)
    ativo = models.BooleanField(default=True, db_index=True)

    criado_em = models.DateTimeField(auto_now_add=True)
    indexado_em = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["nome_arquivo"]
        verbose_name = "Índice de arquivo KM"
        verbose_name_plural = "Índice de arquivos KM"
        indexes = [
            models.Index(fields=["ativo", "extensao"]),
            models.Index(fields=["ativo", "eh_transmittal_letter"]),
            models.Index(fields=["documento_extraido"]),
        ]

    def __str__(self):
        return self.nome_arquivo

class PCFTimeline(models.Model):
    tipo = models.CharField(max_length=50, blank=True)

    caminho = models.TextField(blank=True)
    pcf_link = models.CharField(max_length=255, blank=True)

    numero_pcf = models.CharField(max_length=255, blank=True)
    numero_documento = models.CharField(max_length=255, blank=True)

    titulo = models.TextField(blank=True)

    revisao_pcf = models.CharField(max_length=50, blank=True)

    data_recebimento = models.CharField(max_length=50, blank=True)

    open_comments = models.IntegerField(default=0)
    qtd_comentarios = models.IntegerField(default=0)

    status_final = models.CharField(max_length=255, blank=True)

    atualizado_em = models.DateTimeField(auto_now=True)
    criado_em = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = ("tipo", "numero_documento", "revisao_pcf", "pcf_link")
        ordering = ["numero_documento", "revisao_pcf"]

    def __str__(self):
        return f"{self.tipo} - {self.numero_documento} - {self.revisao_pcf}"

class DocumentoLD(models.Model):
    origem_aba = models.CharField(max_length=100, blank=True)
    documento = models.CharField(max_length=255, blank=True)
    revisao = models.CharField(max_length=50, blank=True)

    titulo = models.TextField(blank=True)
    disciplina = models.CharField(max_length=100, blank=True)

    status_documento = models.CharField(max_length=100, blank=True)
    status_grd = models.CharField(max_length=100, blank=True)

    grd = models.CharField(max_length=255, blank=True)
    data_grd = models.CharField(max_length=50, blank=True)

    pcf = models.CharField(max_length=255, blank=True)
    data_pcf = models.CharField(max_length=50, blank=True)

    status_final_pcf = models.CharField(max_length=255, blank=True)

    pcf_resposta = models.CharField(max_length=255, blank=True)
    data_resposta = models.CharField(max_length=50, blank=True)

    grd_resposta = models.CharField(max_length=255, blank=True)

    caminho_documento = models.TextField(blank=True)
    caminho_grd = models.TextField(blank=True)
    caminho_pcf = models.TextField(blank=True)
    caminho_resposta = models.TextField(blank=True)
    caminho_grd_resposta = models.TextField(blank=True)

    atualizado_em = models.DateTimeField(auto_now=True)
    criado_em = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["origem_aba", "documento", "revisao"]
        constraints = [
            models.UniqueConstraint(
                fields=["origem_aba", "documento", "revisao"],
                name="uniq_documentold_origem_documento_revisao",
            )
        ]

    def __str__(self):
        return f"{self.documento} R{self.revisao}"

