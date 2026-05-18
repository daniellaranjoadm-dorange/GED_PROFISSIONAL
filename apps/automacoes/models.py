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

    STATUS_VINCULO_KM_AUTO = "AUTO"
    STATUS_VINCULO_KM_MANUAL = "MANUAL"
    STATUS_VINCULO_KM_PENDENTE = "PENDENTE"
    STATUS_VINCULO_KM_CONFLITO = "CONFLITO"
    STATUS_VINCULO_KM_SEM_MATCH = "SEM_MATCH"
    STATUS_VINCULO_KM_MULTIPLO = "MULTIPLO"

    STATUS_VINCULO_KM_CHOICES = [
        (STATUS_VINCULO_KM_AUTO, "Vinculado automaticamente"),
        (STATUS_VINCULO_KM_MANUAL, "Vinculado manualmente"),
        (STATUS_VINCULO_KM_PENDENTE, "Pendente"),
        (STATUS_VINCULO_KM_CONFLITO, "Conflito"),
        (STATUS_VINCULO_KM_SEM_MATCH, "Sem correspondência"),
        (STATUS_VINCULO_KM_MULTIPLO, "Múltiplas correspondências"),
    ]


    STATUS_REVISAO_KM_OK = "OK"
    STATUS_REVISAO_KM_DIVERGENTE = "DIVERGENTE"
    STATUS_REVISAO_KM_PENDENTE = "PENDENTE"
    STATUS_REVISAO_KM_SEM_REVISAO = "SEM_REVISAO"

    STATUS_REVISAO_KM_CHOICES = [
        (STATUS_REVISAO_KM_OK, "Revisão compatível"),
        (STATUS_REVISAO_KM_DIVERGENTE, "Revisão divergente"),
        (STATUS_REVISAO_KM_PENDENTE, "Revisão pendente"),
        (STATUS_REVISAO_KM_SEM_REVISAO, "Sem revisão KM"),
    ]

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

    # ========================================================
    # VÍNCULO KM ↔ LD/PETROBRAS
    # ========================================================
    numero_documento_km = models.CharField(
        max_length=255,
        blank=True,
        db_index=True,
        help_text="Número do documento KM vinculado ao documento Petrobras/Transpetro.",
    )
    transmittal_km = models.CharField(
        max_length=100,
        blank=True,
        db_index=True,
        help_text="Último transmittal KM relacionado a este documento.",
    )
    data_recebimento_km = models.CharField(
        max_length=50,
        blank=True,
        help_text="Data de recebimento do documento via transmittal KM.",
    )
    arquivo_km_encontrado = models.BooleanField(
        default=False,
        db_index=True,
        help_text="Indica se o arquivo físico KM foi localizado no índice de rede.",
    )
    status_vinculo_km = models.CharField(
        max_length=30,
        choices=STATUS_VINCULO_KM_CHOICES,
        default=STATUS_VINCULO_KM_PENDENTE,
        db_index=True,
        help_text="Status do vínculo entre o documento KM e a LD Petrobras.",
    )
    score_vinculo_km = models.PositiveSmallIntegerField(
        default=0,
        db_index=True,
        help_text="Pontuação de confiança do vínculo KM ↔ LD, de 0 a 100.",
    )
    observacao_vinculo_km = models.TextField(
        blank=True,
        help_text="Observações operacionais do motor de vínculo KM ↔ LD.",
    )

    revisao_km = models.CharField(
        max_length=50,
        blank=True,
        db_index=True,
        help_text="Revisão identificada no recebimento KM/transmittal.",
    )
    status_revisao_km = models.CharField(
        max_length=30,
        choices=STATUS_REVISAO_KM_CHOICES,
        default=STATUS_REVISAO_KM_PENDENTE,
        db_index=True,
        help_text="Status comparativo entre revisão KM e revisão LD/Petrobras.",
    )
    observacao_revisao_km = models.TextField(
        blank=True,
        help_text="Observações da comparação de revisão KM ↔ LD.",
    )

    atualizado_em = models.DateTimeField(auto_now=True)
    criado_em = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["origem_aba", "documento", "revisao"]
        indexes = [
            models.Index(fields=["origem_aba", "numero_documento_km"]),
            models.Index(fields=["status_vinculo_km", "score_vinculo_km"]),
            models.Index(fields=["transmittal_km"]),
            models.Index(fields=["status_revisao_km", "revisao_km"]),
        ]
        constraints = [
            models.UniqueConstraint(
                fields=["origem_aba", "documento", "revisao"],
                name="uniq_documentold_origem_documento_revisao",
            )
        ]

    def __str__(self):
        return f"{self.documento} R{self.revisao}"


class JobExecution(models.Model):
    STATUS_PENDING = "PENDING"
    STATUS_RUNNING = "RUNNING"
    STATUS_SUCCESS = "SUCCESS"
    STATUS_FAILED = "FAILED"

    STATUS_CHOICES = [
        (STATUS_PENDING, "Pending"),
        (STATUS_RUNNING, "Running"),
        (STATUS_SUCCESS, "Success"),
        (STATUS_FAILED, "Failed"),
    ]

    job_name = models.CharField(max_length=255)
    status = models.CharField(
        max_length=20,
        choices=STATUS_CHOICES,
        default=STATUS_PENDING,
    )
    payload = models.JSONField(blank=True, null=True)
    result = models.JSONField(blank=True, null=True)
    error = models.TextField(blank=True, null=True)
    duration_ms = models.PositiveIntegerField(blank=True, null=True)
    started_at = models.DateTimeField(blank=True, null=True)
    finished_at = models.DateTimeField(blank=True, null=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        blank=True,
        null=True,
    )

    class Meta:
        ordering = ["-created_at"]
        indexes = [
            models.Index(fields=["job_name", "status"]),
            models.Index(fields=["status", "created_at"]),
        ]

    def __str__(self):
        return f"{self.job_name} [{self.status}]"


class SchedulerState(models.Model):
    STATUS_IDLE = "IDLE"
    STATUS_RUNNING = "RUNNING"
    STATUS_SUCCESS = "SUCCESS"
    STATUS_FAILED = "FAILED"
    STATUS_DISABLED = "DISABLED"

    STATUS_CHOICES = [
        (STATUS_IDLE, "Idle"),
        (STATUS_RUNNING, "Running"),
        (STATUS_SUCCESS, "Success"),
        (STATUS_FAILED, "Failed"),
        (STATUS_DISABLED, "Disabled"),
    ]

    job_name = models.CharField(max_length=255, unique=True, db_index=True)
    enabled = models.BooleanField(default=True, db_index=True)

    last_run_at = models.DateTimeField(blank=True, null=True)
    next_run_at = models.DateTimeField(blank=True, null=True)
    last_success_at = models.DateTimeField(blank=True, null=True)
    last_failure_at = models.DateTimeField(blank=True, null=True)

    last_status = models.CharField(
        max_length=20,
        choices=STATUS_CHOICES,
        default=STATUS_IDLE,
        db_index=True,
    )

    heartbeat_at = models.DateTimeField(blank=True, null=True)
    runtime_notes = models.TextField(blank=True)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["job_name"]
        indexes = [
            models.Index(fields=["enabled", "last_status"]),
            models.Index(fields=["heartbeat_at"]),
            models.Index(fields=["next_run_at"]),
        ]

    def __str__(self):
        return f"{self.job_name} [{self.last_status}]"


class RuntimeAlert(models.Model):
    SEVERITY_INFO = "INFO"
    SEVERITY_WARNING = "WARNING"
    SEVERITY_ERROR = "ERROR"
    SEVERITY_CRITICAL = "CRITICAL"

    SEVERITY_CHOICES = [
        (SEVERITY_INFO, "Info"),
        (SEVERITY_WARNING, "Warning"),
        (SEVERITY_ERROR, "Error"),
        (SEVERITY_CRITICAL, "Critical"),
    ]

    titulo = models.CharField(max_length=255)
    codigo = models.CharField(max_length=100, db_index=True)

    severidade = models.CharField(
        max_length=20,
        choices=SEVERITY_CHOICES,
        default=SEVERITY_WARNING,
        db_index=True,
    )

    job_name = models.CharField(
        max_length=255,
        blank=True,
        db_index=True,
    )

    mensagem = models.TextField()

    detalhes = models.JSONField(
        default=dict,
        blank=True,
    )

    resolvido = models.BooleanField(
        default=False,
        db_index=True,
    )

    resolvido_em = models.DateTimeField(
        null=True,
        blank=True,
    )

    criado_em = models.DateTimeField(
        auto_now_add=True,
        db_index=True,
    )

    class Meta:
        ordering = ["-criado_em"]

    def __str__(self):
        return f"{self.severidade} - {self.titulo}"


# ============================================================
# RUNTIME METRICS PERSISTENCE
# ============================================================

class RuntimeMetricSnapshot(models.Model):
    """
    Lightweight persisted runtime metrics snapshot.

    SQLite-safe:
    - no custom indexes
    - no constraints beyond simple fields
    - append-only operational history
    """

    source = models.CharField(max_length=40, default="manual")
    captured_at = models.DateTimeField(auto_now_add=True)

    runtime_score = models.PositiveSmallIntegerField(default=0)
    runtime_status = models.CharField(max_length=30, default="unknown")

    active_alerts = models.PositiveIntegerField(default=0)
    failed_jobs = models.PositiveIntegerField(default=0)
    running_jobs = models.PositiveIntegerField(default=0)
    stale_scheduler_states = models.PositiveIntegerField(default=0)

    jobs_today = models.PositiveIntegerField(default=0)
    success_today = models.PositiveIntegerField(default=0)
    failed_today = models.PositiveIntegerField(default=0)
    success_rate = models.FloatField(default=0)
    avg_duration = models.FloatField(null=True, blank=True)

    scheduler_total = models.PositiveIntegerField(default=0)
    scheduler_enabled = models.PositiveIntegerField(default=0)
    scheduler_disabled = models.PositiveIntegerField(default=0)

    total_jobs = models.PositiveIntegerField(default=0)
    total_alerts = models.PositiveIntegerField(default=0)

    class Meta:
        ordering = ["-captured_at"]
        verbose_name = "Runtime Metric Snapshot"
        verbose_name_plural = "Runtime Metric Snapshots"

    def __str__(self):
        return f"{self.captured_at:%Y-%m-%d %H:%M:%S} | {self.runtime_status} | {self.runtime_score}"
