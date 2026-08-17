from django.conf import settings
from django.db import models


class GuiaEmissao(models.Model):
    numero = models.CharField(max_length=100, unique=True, db_index=True)
    caminho_guia = models.TextField()
    pasta_documentos = models.TextField()
    data_emissao = models.DateTimeField(null=True, blank=True, db_index=True)
    remetente = models.CharField(max_length=180)
    email_remetente = models.EmailField(blank=True)
    processada_por = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="guias_emissao_processadas",
    )
    criado_em = models.DateTimeField(auto_now_add=True)
    atualizado_em = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-data_emissao", "-criado_em"]
        verbose_name = "Guia de emissão"
        verbose_name_plural = "Guias de emissão"

    def __str__(self):
        return self.numero


class DistribuicaoCopia(models.Model):
    STATUS_EMITIDA = "EMITIDA"
    STATUS_ENTREGUE = "ENTREGUE"
    STATUS_RECOLHIMENTO_PENDENTE = "RECOLHIMENTO_PENDENTE"
    STATUS_RECOLHIDA = "RECOLHIDA"
    STATUS_SUBSTITUIDA = "SUBSTITUIDA"
    STATUS_CANCELADA = "CANCELADA"
    STATUS_EXTRAVIADA = "EXTRAVIADA"
    STATUS_CHOICES = [
        (STATUS_EMITIDA, "Cópia gerada / entrega não confirmada"),
        (STATUS_ENTREGUE, "Entrega confirmada"),
        (STATUS_RECOLHIMENTO_PENDENTE, "Recolhimento pendente"),
        (STATUS_RECOLHIDA, "Recolhida"),
        (STATUS_SUBSTITUIDA, "Substituída"),
        (STATUS_CANCELADA, "Cancelada"),
        (STATUS_EXTRAVIADA, "Extraviada/justificada"),
    ]
    MEIO_NAO_INFORMADO = "NAO_INFORMADO"
    MEIO_FISICO = "FISICO"
    MEIO_DIGITAL = "DIGITAL"
    MEIO_CHOICES = [
        (MEIO_NAO_INFORMADO, "Não informado"),
        (MEIO_FISICO, "Cópia física"),
        (MEIO_DIGITAL, "Cópia digital"),
    ]

    guia = models.ForeignKey(
        GuiaEmissao,
        on_delete=models.PROTECT,
        related_name="distribuicoes",
    )
    documento = models.CharField(max_length=255, db_index=True)
    documento_normalizado = models.CharField(max_length=255, db_index=True)
    revisao = models.CharField(max_length=40, blank=True, db_index=True)
    arquivo_origem = models.TextField()
    destinatario = models.CharField(max_length=180, db_index=True)
    email_destinatario = models.EmailField(blank=True)
    recebedor_carimbo = models.CharField(max_length=180, blank=True, db_index=True)
    meio_distribuicao = models.CharField(
        max_length=20,
        choices=MEIO_CHOICES,
        default=MEIO_NAO_INFORMADO,
        db_index=True,
    )
    quantidade = models.PositiveSmallIntegerField(default=1)
    caminho_copia = models.TextField()
    status = models.CharField(
        max_length=40,
        choices=STATUS_CHOICES,
        default=STATUS_EMITIDA,
        db_index=True,
    )
    emitida_em = models.DateTimeField(db_index=True)
    entregue_em = models.DateTimeField(null=True, blank=True, db_index=True)
    entregue_por = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="copias_controladas_entregues",
    )
    recolhida_em = models.DateTimeField(null=True, blank=True)
    recolhida_por = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="copias_controladas_recolhidas",
    )
    observacao = models.TextField(blank=True)
    criado_em = models.DateTimeField(auto_now_add=True)
    atualizado_em = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-emitida_em", "documento", "destinatario"]
        constraints = [
            models.UniqueConstraint(
                fields=["guia", "documento_normalizado", "revisao", "destinatario"],
                name="uniq_distribuicao_guia_doc_rev_dest",
            )
        ]
        indexes = [
            models.Index(fields=["documento_normalizado", "revisao", "status"]),
            models.Index(fields=["destinatario", "status"]),
        ]
        verbose_name = "Distribuição de cópia"
        verbose_name_plural = "Distribuições de cópias"

    def __str__(self):
        return f"{self.documento} Rev. {self.revisao} - {self.destinatario}"
