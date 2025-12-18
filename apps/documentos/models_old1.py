from django.db import models
from django.conf import settings
from django.contrib.auth.models import Group
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

    def __str__(self):
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

    def __str__(self):
        return f"{self.ordem} - {self.nome} ({self.codigo})"


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

    # 🟣 vínculo com o Workflow Enterprise
    etapa = models.ForeignKey(
        WorkflowEtapa,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="documentos",
        verbose_name="Etapa atual do workflow",
    )

    class Meta:
        verbose_name = "Documento"
        verbose_name_plural = "Documentos"
        ordering = ["codigo", "revisao"]

    def __str__(self):
        return f"{self.codigo} - Rev {self.revisao}"

    # Compatibilidade com templates antigos
    @property
    def etapa_atual(self):
        return self.etapa.nome if self.etapa else None

    # =====================================================
    # 🔄 AVANÇAR ETAPA (ENTERPRISE) + ANEXOS
    # =====================================================
    def enviar_para_proxima_etapa(self, usuario=None, observacao=None, anexos=None):
        """
        Avança o documento para a próxima etapa do workflow.
        anexos: lista de arquivos (ex.: request.FILES.getlist("anexos"))
        """

        # Se ainda não tem etapa, assume a primeira etapa ativa (ordem mais baixa)
        if self.etapa is None:
            nova_etapa = WorkflowEtapa.objects.filter(ativa=True).order_by("ordem").first()
        else:
            # Tenta usar a proxima_etapa configurada no banco
            if self.etapa.proxima_etapa and self.etapa.proxima_etapa.ativa:
                nova_etapa = self.etapa.proxima_etapa
            else:
                # fallback: próxima etapa pela ordem
                nova_etapa = (
                    WorkflowEtapa.objects.filter(ativa=True, ordem__gt=self.etapa.ordem)
                    .order_by("ordem")
                    .first()
                )

        if not nova_etapa:
            return None  # última etapa

        self.etapa = nova_etapa
        self.save(update_fields=["etapa"])

        # Cria histórico
        historico = DocumentoWorkflowHistorico.objects.create(
            documento=self,
            etapa=nova_etapa,
            usuario=usuario,
            acao="AVANCAR",
            observacao=observacao or f"Avanço para {nova_etapa.nome}",
            data=timezone.now(),
        )

        # Salva anexos vinculados ao histórico
        if anexos:
            for f in anexos:
                DocumentoWorkflowHistoricoAnexo.objects.create(
                    historico=historico,
                    arquivo=f,
                    nome_original=getattr(f, "name", ""),
                    enviado_por=usuario,
                )

        return nova_etapa

    # =====================================================
    # 🔄 RETORNAR ETAPA (ENTERPRISE) + ANEXOS
    # =====================================================
    def retornar_etapa(self, etapa_destino, usuario=None, motivo="", anexos=None):
        """
        Retorna o documento para uma etapa específica do workflow.
        etapa_destino pode ser:
            - instancia de WorkflowEtapa
            - id (pk) de WorkflowEtapa
            - código técnico (ex: 'ELABORACAO')
        anexos: lista de arquivos (ex.: request.FILES.getlist("anexos"))
        """

        # Resolver etapa_destino para instancia de WorkflowEtapa
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

        etapa_anterior = self.etapa
        self.etapa = nova_etapa
        self.save(update_fields=["etapa"])

        historico = DocumentoWorkflowHistorico.objects.create(
            documento=self,
            etapa=nova_etapa,
            usuario=usuario,
            acao="RETORNAR",
            observacao=motivo
            or f"Retorno de {etapa_anterior.nome if etapa_anterior else 'N/A'} para {nova_etapa.nome}",
            data=timezone.now(),
        )

        if anexos:
            for f in anexos:
                DocumentoWorkflowHistoricoAnexo.objects.create(
                    historico=historico,
                    arquivo=f,
                    nome_original=getattr(f, "name", ""),
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

    def __str__(self):
        return f"{self.nome_original or 'Arquivo'} → {self.documento.codigo}"

    @property
    def extensao(self):
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

    def __str__(self):
        return f"{self.documento.codigo} - Rev {self.numero_revisao}"


# ======================================================================
# 👷 RESPONSÁVEL POR DISCIPLINA
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
# 📊 STATUS ATUAL DO WORKFLOW POR DOCUMENTO (SLA / PRAZOS)
# ======================================================================
class DocumentoWorkflowStatus(models.Model):
    documento = models.OneToOneField(Documento, on_delete=models.CASCADE, related_name="workflow_status")
    etapa = models.ForeignKey(WorkflowEtapa, on_delete=models.SET_NULL, null=True, blank=True)
    iniciado_em = models.DateTimeField(auto_now_add=True)
    prazo_final = models.DateTimeField(null=True, blank=True)

    @property
    def atrasado(self):
        return self.prazo_final and timezone.now() > self.prazo_final

    def __str__(self):
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
    data = models.DateTimeField(default=timezone.now)

    class Meta:
        ordering = ["-data"]
        verbose_name = "Histórico de Workflow"
        verbose_name_plural = "Histórico de Workflow"

    def __str__(self):
        return (
            f"{self.documento.codigo} - {self.etapa.nome if self.etapa else 'N/A'} "
            f"- {self.get_acao_display()}"
        )


# ======================================================================
# 📎 ANEXOS DO HISTÓRICO DO WORKFLOW (AVANÇO/RETORNO)
# ======================================================================
class DocumentoWorkflowHistoricoAnexo(models.Model):
    historico = models.ForeignKey(
        DocumentoWorkflowHistorico,
        on_delete=models.CASCADE,
        related_name="anexos",
    )
    arquivo = models.FileField(upload_to="workflow_anexos/%Y/%m/")
    nome_original = models.CharField(max_length=255, blank=True, null=True)
    enviado_por = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
    )
    enviado_em = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-enviado_em"]
        verbose_name = "Anexo do Histórico do Workflow"
        verbose_name_plural = "Anexos do Histórico do Workflow"

    def __str__(self):
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

    def __str__(self):
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

    def __str__(self):
        u = self.usuario.username if self.usuario else "Sistema"
        d = self.documento.codigo if self.documento else "Sem doc"
        return f"{self.acao} - {d} - {u}"


def registrar_log(usuario, documento, acao, descricao=None):
    LogAuditoria.objects.create(
        usuario=usuario,
        documento=documento,
        acao=acao,
        descricao=descricao,
    )


# ======================================================================
# 💼 FINANCEIRO DO PROJETO
# ======================================================================
class ProjetoFinanceiro(models.Model):
    projeto = models.ForeignKey(Projeto, on_delete=models.CASCADE, related_name="financeiro")
    fase = models.CharField(max_length=50)  # Basico/Aprovado/Asbuilt
    valor_total_usd = models.DecimalField(max_digits=12, decimal_places=2)

    descricao = models.CharField(max_length=255, null=True, blank=True)
    moeda = models.CharField(max_length=10, default="USD")

    def __str__(self):
        return f"{self.projeto.nome} - {self.fase} - {self.valor_total_usd} USD"
