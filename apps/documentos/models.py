from __future__ import annotations

from datetime import timedelta
from django.conf import settings
from django.contrib.auth.models import Group
from django.db import models
from django.utils import timezone


# ==========================
# ESTADOS OFICIAIS WORKFLOW (LEGADO / REFERÊNCIA)
# ==========================
WORKFLOW_ESTADOS = [
    ("ELABORACAO", "Documento em Elaboração"),
    ("REVISAO_INTERNA", "Revisão Interna"),
    ("APROVACAO_TECNICA", "Aprovação Técnica"),
    ("DOC_CONTROL", "Doc Control"),
    ("ENVIADO_CLIENTE", "Enviado ao Cliente"),
    ("APROVACAO_CLIENTE", "Aprovação Cliente (PCF)"),
    ("EMISSAO_FINAL", "Emissão Final"),
]


# ======================================================================
# 🏗 PROJETO — BASE MULTI-CONTRATO
# ======================================================================
class Projeto(models.Model):
    nome = models.CharField(max_length=120, unique=True)
    cliente = models.CharField(max_length=120, blank=True, null=True)

    pasta_base = models.CharField(
        max_length=500,
        help_text="Caminho base onde serão criadas as pastas GRDT/GED",
    )

    prefixo_ged = models.CharField(max_length=50, default="GED")
    ativo = models.BooleanField(default=True)
    criado_em = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = "Projeto"
        verbose_name_plural = "Projetos"

    def __str__(self) -> str:
        return self.nome


# ======================================================================
# 🔁 WORKFLOW ENTERPRISE – ETAPAS PARAMETRIZADAS
# ======================================================================
class WorkflowEtapa(models.Model):
    codigo = models.CharField(
        max_length=50,
        choices=WORKFLOW_ESTADOS,
        unique=True,
        verbose_name="Código técnico da etapa",
        help_text="Identificador interno da etapa (ex: ELABORACAO, DOC_CONTROL).",
    )
    nome = models.CharField(
        max_length=100,
        verbose_name="Nome exibido da etapa",
        help_text="Nome amigável exibido nas telas (ex: Documento em Elaboração).",
    )
    ordem = models.PositiveIntegerField(
        verbose_name="Ordem no fluxo",
        help_text="1 = primeira etapa, 2 = segunda, etc.",
    )
    prazo_dias = models.PositiveIntegerField(
        default=15,
        verbose_name="Prazo (dias)",
        help_text="SLA padrão em dias para esta etapa.",
    )
    grupos_responsaveis = models.ManyToManyField(
        Group,
        blank=True,
        verbose_name="Grupos responsáveis pela etapa",
        help_text="Grupos de usuários que podem atuar nesta etapa (ex: Elaboradores).",
    )
    ativa = models.BooleanField(default=True, verbose_name="Etapa ativa?")
    proxima_etapa = models.ForeignKey(
        "self",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="etapas_anteriores",
        verbose_name="Próxima etapa padrão",
        help_text="Etapa de destino quando o documento é avançado a partir desta etapa.",
    )

    class Meta:
        ordering = ["ordem"]
        verbose_name = "Etapa de Workflow"
        verbose_name_plural = "Etapas de Workflow"

    def __str__(self) -> str:
        return f"{self.ordem} - {self.nome} ({self.codigo})"


# ======================================================================
# 🔀 TRANSIÇÕES PERMITIDAS (NOVO - migration 0017)
# ======================================================================
class WorkflowTransicao(models.Model):
    origem = models.ForeignKey(
        WorkflowEtapa,
        on_delete=models.CASCADE,
        related_name="transicoes_origem",
    )
    destino = models.ForeignKey(
        WorkflowEtapa,
        on_delete=models.CASCADE,
        related_name="transicoes_destino",
    )
    ativa = models.BooleanField(default=True)

    class Meta:
        verbose_name = "Transição de Workflow"
        verbose_name_plural = "Transições de Workflow"
        constraints = [
            models.UniqueConstraint(fields=["origem", "destino"], name="uniq_transicao_origem_destino"),
        ]

    def __str__(self) -> str:
        return f"{self.origem.codigo} → {self.destino.codigo}"


# ======================================================================
# 📄 DOCUMENTO CENTRAL DO GED
# ======================================================================
class Documento(models.Model):
    projeto = models.ForeignKey(
        Projeto,
        on_delete=models.CASCADE,
        related_name="documentos",
        null=True,
        blank=True,
    )

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

    valor_brl = models.DecimalField("Valor (R$)", max_digits=15, decimal_places=2, null=True, blank=True)
    valor_usd = models.DecimalField("Valor (USD)", max_digits=15, decimal_places=2, null=True, blank=True)

    ged_interna = models.CharField(max_length=50, blank=True, null=True)
    criado_em = models.DateTimeField(auto_now_add=True)
    ativo = models.BooleanField(default=True)

    deletado_em = models.DateTimeField(blank=True, null=True)
    deletado_por = models.CharField(max_length=200, blank=True, null=True)
    motivo_exclusao = models.CharField(max_length=255, blank=True, null=True)

    # Etapa oficial (FK)
    etapa = models.ForeignKey(
        WorkflowEtapa,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="documentos",
        verbose_name="Etapa atual do workflow",
    )

    # Etapa legada (string) - migration 0017
    etapa_atual = models.CharField(max_length=50, blank=True, null=True)

    class Meta:
        verbose_name = "Documento"
        verbose_name_plural = "Documentos"
        ordering = ["codigo", "revisao"]

    def __str__(self) -> str:
        return f"{self.codigo} - Rev {self.revisao}"

    def _atualizar_status_workflow(self, nova_etapa: WorkflowEtapa | None):
        """Atualiza/Cria DocumentoWorkflowStatus com SLA."""
        if not nova_etapa:
            return
        status, _ = DocumentoWorkflowStatus.objects.get_or_create(documento=self)
        status.etapa = nova_etapa
        status.iniciado_em = timezone.now()
        status.prazo_final = timezone.now() + timedelta(days=int(nova_etapa.prazo_dias or 0))
        status.save()

    def enviar_para_proxima_etapa(self, usuario=None, observacao: str | None = None, anexos=None):
        """
        Avança para próxima etapa:
        - tenta proxima_etapa configurada
        - tenta WorkflowTransicao (se houver)
        - fallback por ordem
        """
        etapa_atual_fk = self.etapa

        # 1) se não tem etapa ainda, assume primeira ativa
        if etapa_atual_fk is None:
            nova_etapa = WorkflowEtapa.objects.filter(ativa=True).order_by("ordem").first()
        else:
            # 2) proxima_etapa configurada
            if etapa_atual_fk.proxima_etapa and etapa_atual_fk.proxima_etapa.ativa:
                nova_etapa = etapa_atual_fk.proxima_etapa
            else:
                # 3) transição permitida (menor ordem destino)
                trans = (
                    WorkflowTransicao.objects.filter(origem=etapa_atual_fk, ativa=True, destino__ativa=True)
                    .select_related("destino")
                    .order_by("destino__ordem")
                    .first()
                )
                if trans:
                    nova_etapa = trans.destino
                else:
                    # 4) fallback por ordem
                    nova_etapa = (
                        WorkflowEtapa.objects.filter(ativa=True, ordem__gt=etapa_atual_fk.ordem)
                        .order_by("ordem")
                        .first()
                    )

        if not nova_etapa:
            return None

        self.etapa = nova_etapa
        self.etapa_atual = nova_etapa.codigo
        self.save(update_fields=["etapa", "etapa_atual"])

        self._atualizar_status_workflow(nova_etapa)

        hist = DocumentoWorkflowHistorico.objects.create(
            documento=self,
            etapa=nova_etapa,
            usuario=usuario,
            acao="AVANCAR",
            observacao=observacao or f"Avançado para {nova_etapa.nome}",
            data=timezone.now(),
        )

        for f in (anexos or []):
            DocumentoWorkflowHistoricoAnexo.objects.create(
                historico=hist,
                arquivo=f,
                nome_original=getattr(f, "name", None),
                enviado_por=usuario,
            )

        return nova_etapa

    def retornar_etapa(self, etapa_destino, usuario=None, motivo: str | None = None, anexos=None):
        """
        Retorna o documento para uma etapa específica.
        etapa_destino pode ser instância, pk (int) ou código (str).
        """
        if isinstance(etapa_destino, WorkflowEtapa):
            nova_etapa = etapa_destino
        elif isinstance(etapa_destino, int):
            nova_etapa = WorkflowEtapa.objects.filter(pk=etapa_destino).first()
        elif isinstance(etapa_destino, str):
            nova_etapa = WorkflowEtapa.objects.filter(codigo=etapa_destino).first()
        else:
            nova_etapa = None

        if not nova_etapa or not nova_etapa.ativa:
            return None

        self.etapa = nova_etapa
        self.etapa_atual = nova_etapa.codigo
        self.save(update_fields=["etapa", "etapa_atual"])

        self._atualizar_status_workflow(nova_etapa)

        hist = DocumentoWorkflowHistorico.objects.create(
            documento=self,
            etapa=nova_etapa,
            usuario=usuario,
            acao="RETORNAR",
            observacao=motivo or f"Retornado para {nova_etapa.nome}",
            data=timezone.now(),
        )

        for f in (anexos or []):
            DocumentoWorkflowHistoricoAnexo.objects.create(
                historico=hist,
                arquivo=f,
                nome_original=getattr(f, "name", None),
                enviado_por=usuario,
            )

        return nova_etapa


# ======================================================================
# 🗂 ANEXOS
# ======================================================================
class ArquivoDocumento(models.Model):
    documento = models.ForeignKey(Documento, on_delete=models.CASCADE, related_name="arquivos")
    arquivo = models.FileField(upload_to="documentos/anexos/")
    nome_original = models.CharField(max_length=255, blank=True, null=True)
    tipo = models.CharField(max_length=20, blank=True, null=True)
    enviado_em = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-enviado_em"]

    def __str__(self) -> str:
        return f"{self.nome_original or 'Arquivo'} → {self.documento.codigo}"

    @property
    def extensao(self) -> str:
        return self.arquivo.name.split(".")[-1].lower()


# ======================================================================
# 🔄 CONTROLE DE VERSÕES
# ======================================================================
class DocumentoVersao(models.Model):
    documento = models.ForeignKey(Documento, on_delete=models.CASCADE, related_name="versoes")
    numero_revisao = models.CharField(max_length=10)
    arquivo = models.FileField(upload_to="documentos/versoes/")
    criado_em = models.DateTimeField(auto_now_add=True)
    criado_por = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True)
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

    def __str__(self) -> str:
        return f"{self.documento.codigo} - Rev {self.numero_revisao}"


class DocumentoReferenciaExterna(models.Model):
    """Identidade do documento em sistemas externos, como DOX, KM ou cliente."""

    SISTEMA_DOX = "DOX"
    SISTEMA_KM = "KM"
    SISTEMA_CLIENTE = "CLIENTE"
    SISTEMA_CHOICES = [
        (SISTEMA_DOX, "DOX"),
        (SISTEMA_KM, "Kongsberg/KM"),
        (SISTEMA_CLIENTE, "Cliente"),
    ]

    documento = models.ForeignKey(
        Documento,
        on_delete=models.CASCADE,
        related_name="referencias_externas",
    )
    sistema = models.CharField(max_length=30, choices=SISTEMA_CHOICES, db_index=True)
    identificador_externo = models.CharField(max_length=255, db_index=True)
    url = models.URLField(max_length=1000, blank=True)
    metadados = models.JSONField(default=dict, blank=True)
    sincronizado_em = models.DateTimeField(null=True, blank=True)
    criado_em = models.DateTimeField(auto_now_add=True)
    atualizado_em = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["sistema", "identificador_externo"]
        constraints = [
            models.UniqueConstraint(
                fields=["sistema", "identificador_externo"],
                name="uniq_referencia_externa_sistema_id",
            )
        ]
        indexes = [models.Index(fields=["documento", "sistema"])]

    def __str__(self) -> str:
        return f"{self.sistema}: {self.identificador_externo}"


# ======================================================================
# 👷 RESPONSÁVEL POR DISCIPLINA
# ======================================================================
class ResponsavelDisciplina(models.Model):
    disciplina = models.CharField(max_length=50, unique=True)
    responsavel = models.CharField(max_length=200)
    email = models.CharField(max_length=200, blank=True, null=True)

    class Meta:
        ordering = ["disciplina"]

    def __str__(self) -> str:
        return f"{self.disciplina} - {self.responsavel}"


# ======================================================================
# 📊 STATUS ATUAL DO WORKFLOW POR DOCUMENTO (SLA / PRAZOS)
# ======================================================================
class DocumentoWorkflowStatus(models.Model):
    documento = models.OneToOneField(Documento, on_delete=models.CASCADE, related_name="workflow_status")
    etapa = models.ForeignKey(WorkflowEtapa, on_delete=models.SET_NULL, null=True, blank=True)
    iniciado_em = models.DateTimeField(auto_now_add=True)
    prazo_final = models.DateTimeField(null=True, blank=True)

    @property
    def atrasado(self) -> bool:
        return bool(self.prazo_final and timezone.now() > self.prazo_final)

    def __str__(self) -> str:
        return f"{self.documento.codigo} → {self.etapa.nome if self.etapa else '(sem etapa)'}"


# ======================================================================
# ✔ HISTÓRICO DE MOVIMENTAÇÃO NO WORKFLOW
# ======================================================================
class DocumentoWorkflowHistorico(models.Model):
    ACOES = [
        ("AVANCAR", "Avançar etapa"),
        ("RETORNAR", "Retornar etapa"),
        ("AJUSTE_MANUAL", "Ajuste manual"),
    ]

    documento = models.ForeignKey(Documento, on_delete=models.CASCADE, related_name="historico_workflow")
    etapa = models.ForeignKey(WorkflowEtapa, on_delete=models.SET_NULL, null=True, blank=True)
    usuario = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True)
    acao = models.CharField(max_length=20, choices=ACOES)
    observacao = models.TextField(blank=True, null=True)
    data = models.DateTimeField()

    class Meta:
        ordering = ["-data"]
        verbose_name = "Histórico de Workflow"
        verbose_name_plural = "Histórico de Workflow"

    def __str__(self) -> str:
        return f"{self.documento.codigo} - {self.etapa.nome if self.etapa else 'N/A'} - {self.get_acao_display()}"


class DocumentoWorkflowHistoricoAnexo(models.Model):
    historico = models.ForeignKey(DocumentoWorkflowHistorico, on_delete=models.CASCADE, related_name="anexos")
    arquivo = models.FileField(upload_to="workflow_anexos/%Y/%m/")
    nome_original = models.CharField(max_length=255, blank=True, null=True)
    enviado_por = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True)
    enviado_em = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-enviado_em"]
        verbose_name = "Anexo do Histórico do Workflow"
        verbose_name_plural = "Anexos do Histórico do Workflow"

    def __str__(self) -> str:
        return self.nome_original or f"Anexo #{self.pk}"


# ======================================================================
# ✔ Aprovações e movimentação dentro do Workflow
# ======================================================================
class DocumentoAprovacao(models.Model):
    documento = models.ForeignKey(Documento, on_delete=models.CASCADE, related_name="aprovacoes")
    etapa = models.ForeignKey(WorkflowEtapa, on_delete=models.SET_NULL, null=True, blank=True)
    usuario = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True)
    data = models.DateTimeField(auto_now_add=True)
    comentario = models.TextField(blank=True, null=True)
    status = models.CharField(
        max_length=50,
        choices=[
            ("aprovado", "Aprovado"),
            ("revisar", "Revisar"),
            ("reprovado", "Reprovado"),
        ],
        default="revisar",
    )

    class Meta:
        ordering = ["-data"]

    def __str__(self) -> str:
        return f"{self.documento.codigo} - {self.etapa} - {self.status}"


# ======================================================================
# 🧾 LOG AUDITORIA
# ======================================================================
class LogAuditoria(models.Model):
    usuario = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True)
    documento = models.ForeignKey(Documento, on_delete=models.SET_NULL, null=True, blank=True, related_name="logs")
    acao = models.CharField(max_length=50)
    descricao = models.TextField(blank=True, null=True)
    data = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-data"]

    def __str__(self) -> str:
        u = self.usuario.username if self.usuario else "Sistema"
        d = self.documento.codigo if self.documento else "Sem doc"
        return f"{self.acao} - {d} - {u}"


def registrar_log(usuario, documento, acao, descricao=None):
    LogAuditoria.objects.create(usuario=usuario, documento=documento, acao=acao, descricao=descricao)


# ======================================================================
# 💼 FINANCEIRO DO PROJETO
# ======================================================================
class ProjetoFinanceiro(models.Model):
    projeto = models.ForeignKey(Projeto, on_delete=models.CASCADE, related_name="financeiro")
    fase = models.CharField(max_length=50)
    valor_total_usd = models.DecimalField(max_digits=12, decimal_places=2)
    descricao = models.CharField(max_length=255, null=True, blank=True)
    moeda = models.CharField(max_length=10, default="USD")

    def __str__(self) -> str:
        return f"{self.projeto.nome} - {self.fase} - {self.valor_total_usd} USD"
