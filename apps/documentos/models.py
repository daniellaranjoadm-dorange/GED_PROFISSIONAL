from django.db import models

from django.conf import settings
from django.contrib.auth.models import Group


# ======================================================================
# 🏗 PROJETO — BASE PARA MULTI-CLIENTE / MULTI-OBRA
# ======================================================================
class Projeto(models.Model):
    """Projeto / contrato / empreendimento.

    Serve como raiz para parametrizar:
    - documentos
    - pastas base na rede
    - prefixos de GED
    - cliente associado
    """

    nome = models.CharField(max_length=120, unique=True)
    cliente = models.CharField(max_length=120, blank=True, null=True)

    pasta_base = models.CharField(
        max_length=500,
        help_text="Caminho base na rede onde serão criadas as pastas de saída (GRDT, GED, etc.)",
    )

    prefixo_ged = models.CharField(
        max_length=50,
        default="GED",
        help_text="Prefixo padrão para numeração de GED interna (ex: GED, GD, DC, etc.)",
    )

    ativo = models.BooleanField(default=True)

    criado_em = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = "Projeto"
        verbose_name_plural = "Projetos"

    def __str__(self) -> str:  # type: ignore[override]
        return self.nome


# ======================================================================
# 📄 MODELO PRINCIPAL — DOCUMENTO
# ======================================================================
class Documento(models.Model):
    """Documento técnico controlado pelo GED.

    Reestruturado para uso profissional e multi-projeto.
    """

    # Vínculo principal
    projeto = models.ForeignKey(
        Projeto,
        on_delete=models.CASCADE,
        related_name="documentos",
        null=True,
        blank=True,
    )

    # Classificação básica
    fase = models.CharField(max_length=50, blank=True, null=True)
    tipo_doc = models.CharField(
    "Tipo de Documento",
    max_length=100,
    null=True,
    blank=True,
)


    # Identificação
    codigo = models.CharField(max_length=200)
    revisao = models.CharField(max_length=10, default="0")
    titulo = models.CharField(max_length=255)
    disciplina = models.CharField(max_length=50, blank=True, null=True)

    # Status principais
    status_documento = models.CharField(
        "Status do Documento",
        max_length=50,
        blank=True,
        null=True,
        help_text="Substitui o antigo 'Status LDP'",
    )

    status_emissao = models.CharField(
        "Status de Emissão",
        max_length=50,
        blank=True,
        null=True,
    )

    # Relacionamento com o cliente (GRDT / resposta)
    grdt_cliente = models.CharField(
        "GRDT Cliente",
        max_length=50,
        blank=True,
        null=True,
    )

    resposta_cliente = models.CharField(
        "Resposta Cliente",
        max_length=255,
        blank=True,
        null=True,
    )

    data_emissao_grdt = models.DateField(
        "Data Emissão GRDT",
        blank=True,
        null=True,
    )

    # GED interna / controle interno de saída
    ged_interna = models.CharField(
        "GED Interna",
        max_length=50,
        blank=True,
        null=True,
        help_text="Identificação interna da GED gerada para este documento (quando aplicável)",
    )

    # Metadados de ciclo de vida
    criado_em = models.DateTimeField(auto_now_add=True)
    ativo = models.BooleanField(default=True)

    deletado_em = models.DateTimeField(blank=True, null=True)
    deletado_por = models.CharField(max_length=200, blank=True, null=True)
    motivo_exclusao = models.CharField(max_length=255, blank=True, null=True)

    # Ponteiro de etapa textual (complementar ao workflow enterprise)
    etapa_atual = models.CharField(
        max_length=100,
        default="Revisão Interna – Disciplina",
    )

    class Meta:
        verbose_name = "Documento"
        verbose_name_plural = "Documentos"
        ordering = ["codigo", "revisao"]

    def __str__(self) -> str:  # type: ignore[override]
        return f"{self.codigo} - Rev {self.revisao}"


# ======================================================================
# 📎 ARQUIVOS DO DOCUMENTO — ANEXOS ATUAIS
# ======================================================================
class ArquivoDocumento(models.Model):
    documento = models.ForeignKey(
        Documento,
        on_delete=models.CASCADE,
        related_name="arquivos",
    )

    arquivo = models.FileField(upload_to="documentos/anexos/")
    nome_original = models.CharField(max_length=255, blank=True, null=True)

    tipo = models.CharField(
        max_length=20,
        blank=True,
        null=True,
        help_text="Classificação opcional do anexo (PDF, DWG, DOCX, etc.)",
    )

    enviado_em = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = "Arquivo do Documento"
        verbose_name_plural = "Arquivos do Documento"
        ordering = ["-enviado_em"]

    def __str__(self) -> str:  # type: ignore[override]
        return f"Anexo {self.nome_original} → {self.documento.codigo}"

    @property
    def extensao(self) -> str:
        try:
            return self.arquivo.name.split(".")[-1].lower()
        except Exception:
            return ""


# ======================================================================
# 📚 CONTROLE DE VERSÕES DO DOCUMENTO
# ======================================================================
class DocumentoVersao(models.Model):
    documento = models.ForeignKey(
        Documento,
        on_delete=models.CASCADE,
        related_name="versoes",
    )

    numero_revisao = models.CharField(
        max_length=10,
        help_text="Número da revisão (ex: 0, 1, A, B, C)",
    )

    arquivo = models.FileField(
        upload_to="documentos/versoes/",
        null=False,
        blank=False,
    )

    criado_em = models.DateTimeField(auto_now_add=True)

    criado_por = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
    )

    observacao = models.TextField(
        blank=True,
        help_text="Descrição das alterações desta revisão",
    )

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
        verbose_name = "Versão do Documento"
        verbose_name_plural = "Versões do Documento"

    def __str__(self) -> str:  # type: ignore[override]
        return f"{self.documento.codigo} - Rev {self.numero_revisao}"


# ======================================================================
# 👤 RESPONSÁVEIS POR DISCIPLINA
# ======================================================================
class ResponsavelDisciplina(models.Model):
    disciplina = models.CharField(max_length=50, unique=True)
    responsavel = models.CharField(max_length=200)
    email = models.CharField(max_length=200, blank=True, null=True)

    class Meta:
        verbose_name = "Responsável por Disciplina"
        verbose_name_plural = "Responsáveis por Disciplina"
        ordering = ["disciplina"]

    def __str__(self) -> str:  # type: ignore[override]
        return f"{self.disciplina} - {self.responsavel}"


# ======================================================================
# 🧠 WORKFLOW ENTERPRISE — CONFIGURAÇÃO DAS ETAPAS
# ======================================================================
class WorkflowEtapa(models.Model):
    """Etapas do fluxo enterprise.

    Exemplo de etapas:
      1 - Revisão Interna – Disciplina
      2 - Aprovação Técnica – Coordenador
      3 - Envio ao Cliente
      4 - Aprovação do Cliente
      5 - Emissão Final
    """

    nome = models.CharField(max_length=100)
    ordem = models.PositiveIntegerField(
        help_text="Ordem do fluxo (1, 2, 3...)",
    )
    prazo_dias = models.PositiveIntegerField(
        default=0,
        help_text="Prazo em dias para conclusão desta etapa (0 = sem prazo)",
    )

    grupos_responsaveis = models.ManyToManyField(
        Group,
        blank=True,
        related_name="etapas_workflow",
        help_text="Grupos de usuários responsáveis por atuar nesta etapa",
    )

    ativa = models.BooleanField(default=True)

    class Meta:
        ordering = ["ordem"]
        verbose_name = "Etapa de Workflow"
        verbose_name_plural = "Etapas de Workflow"

    def __str__(self) -> str:  # type: ignore[override]
        return f"{self.ordem} - {self.nome}"


# ======================================================================
# 📌 STATUS ATUAL DO DOCUMENTO NO WORKFLOW ENTERPRISE
# ======================================================================
class DocumentoWorkflowStatus(models.Model):
    """Ponteiro da etapa atual do documento no fluxo enterprise."""

    documento = models.OneToOneField(
        Documento,
        on_delete=models.CASCADE,
        related_name="workflow_status",
    )

    etapa = models.ForeignKey(
        WorkflowEtapa,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="documentos",
    )

    iniciado_em = models.DateTimeField(
        auto_now_add=True,
        help_text="Início da etapa atual",
    )

    prazo_final = models.DateTimeField(
        null=True,
        blank=True,
        help_text="Data/hora limite calculada em função do prazo da etapa",
    )

    class Meta:
        verbose_name = "Status do Workflow do Documento"
        verbose_name_plural = "Status do Workflow dos Documentos"

    def __str__(self) -> str:  # type: ignore[override]
        if self.etapa:
            return f"{self.documento.codigo} → {self.etapa.nome}"
        return f"{self.documento.codigo} → (sem etapa)"

    @property
    def atrasado(self) -> bool:
        from django.utils import timezone

        if self.prazo_final:
            return timezone.now() > self.prazo_final
        return False


# ======================================================================
# ✅ REGISTRO DE APROVAÇÕES / AÇÕES POR USUÁRIO
# ======================================================================
class DocumentoAprovacao(models.Model):
    """Registro das ações de aprovação/reprovação/comentário por usuário."""

    documento = models.ForeignKey(
        Documento,
        on_delete=models.CASCADE,
        related_name="aprovacoes",
    )

    etapa = models.ForeignKey(
        WorkflowEtapa,
        on_delete=models.CASCADE,
        related_name="aprovacoes",
    )

    usuario = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="aprovacoes_documentos",
    )

    status = models.CharField(
        max_length=20,
        choices=[
            ("PENDENTE", "Pendente"),
            ("APROVADO", "Aprovado"),
            ("REPROVADO", "Reprovado"),
            ("COMENTADO", "Comentado"),
        ],
        default="PENDENTE",
    )

    comentario = models.TextField(blank=True, null=True)
    data = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-data"]
        verbose_name = "Aprovação de Documento"
        verbose_name_plural = "Aprovações de Documentos"

    def __str__(self) -> str:  # type: ignore[override]
        return f"{self.documento.codigo} / {self.etapa.nome} / {self.usuario} → {self.status}"
