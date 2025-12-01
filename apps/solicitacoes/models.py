from django.db import models
from django.conf import settings


class SolicitarAcesso(models.Model):
    STATUS_PENDENTE = "pendente"
    STATUS_APROVADO = "aprovado"
    STATUS_NEGADO = "negado"

    STATUS_CHOICES = [
        (STATUS_PENDENTE, "Pendente"),
        (STATUS_APROVADO, "Aprovado"),
        (STATUS_NEGADO, "Negado"),
    ]

    nome = models.CharField("Nome", max_length=200)
    email = models.EmailField("E-mail")
    setor = models.CharField("Setor", max_length=200, blank=True)
    motivo = models.TextField("Motivo do acesso")

    status = models.CharField(
        "Status",
        max_length=20,
        choices=STATUS_CHOICES,
        default=STATUS_PENDENTE,
    )

    data_solicitacao = models.DateTimeField(
        "Data da solicitação",
        auto_now_add=True,
    )
    data_decisao = models.DateTimeField(
        "Data da decisão",
        null=True,
        blank=True,
    )

    observacao_admin = models.TextField(
        "Observação do administrador",
        blank=True,
    )

    class Meta:
        verbose_name = "Solicitação de acesso"
        verbose_name_plural = "Solicitações de acesso"
        ordering = ["-data_solicitacao"]

    def __str__(self):
        return f"{self.nome} ({self.get_status_display()})"


class AuditoriaSolicitacao(models.Model):
    """
    Registro de auditoria das decisões sobre solicitações de acesso.
    Atende exigências de rastreabilidade (quem aprovou, quando, de onde, etc).
    """

    solicitacao = models.ForeignKey(
        SolicitarAcesso,
        on_delete=models.CASCADE,
        related_name="auditorias",
        verbose_name="Solicitação",
    )

    usuario_responsavel = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="auditorias_solicitacoes",
        verbose_name="Usuário responsável",
    )

    usuario_criado = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="auditorias_usuarios_criados",
        verbose_name="Usuário criado",
    )

    status_anterior = models.CharField(
        "Status anterior",
        max_length=20,
        blank=True,
    )
    status_novo = models.CharField(
        "Status novo",
        max_length=20,
        blank=True,
    )

    ip = models.GenericIPAddressField(
        "IP",
        null=True,
        blank=True,
    )

    observacao = models.TextField(
        "Observação",
        blank=True,
    )

    data_registro = models.DateTimeField(
        "Data do registro",
        auto_now_add=True,
    )

    class Meta:
        verbose_name = "Auditoria de solicitação"
        verbose_name_plural = "Auditorias de solicitação"
        ordering = ["-data_registro"]

    def __str__(self):
        return f"{self.solicitacao_id} - {self.status_anterior} → {self.status_novo}"
