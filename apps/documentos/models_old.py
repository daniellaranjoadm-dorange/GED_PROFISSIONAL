from django.db import models
from django.conf import settings
from django.contrib.auth.models import Group
# ==========================
# ESTADOS OFICIAIS WORKFLOW
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
        help_text="Caminho base onde serão criadas as pastas GRDT/GED"
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
    projeto = models.ForeignKey(
        Projeto, on_delete=models.CASCADE,
        related_name="documentos",
        null=True, blank=True
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

    etapa_atual = models.CharField(
        max_length=100,
        choices=WORKFLOW_ESTADOS,
        default="ELABORACAO"
    )

    class Meta:
        verbose_name = "Documento"
        verbose_name_plural = "Documentos"
        ordering = ["codigo", "revisao"]

    def __str__(self):
        return f"{self.codigo} - Rev {self.revisao}"

    # =====================================================
    # MAPEAMENTO AUTOMÁTICO — ETAPAS ANTIGAS → NOVAS
    # =====================================================
    MAPA_ETAPAS = {
        "Elaboração": "ELABORACAO",
        "Documento em Elaboração": "ELABORACAO",

        "Revisão Interna": "REVISAO_INTERNA",
        "Revisão Interna – Disciplina": "REVISAO_INTERNA",

        "Aprovação Técnica": "APROVACAO_TECNICA",
        "Aprovação Técnica – Coordenador": "APROVACAO_TECNICA",
        "Aprovação Técnica – Engenheiro": "APROVACAO_TECNICA",

        "Doc Control": "DOC_CONTROL",

        "Envio ao Cliente": "ENVIADO_CLIENTE",
        "Enviado ao Cliente": "ENVIADO_CLIENTE",

        "Aprovação Cliente": "APROVACAO_CLIENTE",
        "Aprovação do Cliente": "APROVACAO_CLIENTE",

        "Emissão Final": "EMISSAO_FINAL",
    }
    # =====================================================
    # AVANÇAR ETAPA
    # =====================================================
    def enviar_para_proxima_etapa(self, usuario=None):

        # Importa função correta de log
        from apps.documentos.views import registrar_workflow

        etapa_atual = self.MAPA_ETAPAS.get(self.etapa_atual, self.etapa_atual)

        fluxo = [
            "ELABORACAO",
            "REVISAO_INTERNA",
            "APROVACAO_TECNICA",
            "DOC_CONTROL",
            "ENVIADO_CLIENTE",
            "APROVACAO_CLIENTE",
            "EMISSAO_FINAL",
        ]

        if etapa_atual not in fluxo:
            return False

        idx = fluxo.index(etapa_atual)

        if idx == len(fluxo) - 1:
            return False  # já está na última etapa

        nova = fluxo[idx + 1]

        self.etapa_atual = nova
        self.save(update_fields=["etapa_atual"])

        # Log de workflow
        registrar_workflow(
            documento=self,
            etapa=nova,
            status="Avançado",
            request=None,
            observacao=f"{etapa_atual} → {nova}"
        )

        return nova

    # =====================================================
    # RETORNAR ETAPA
    # =====================================================
def retornar_etapa(self, etapa_destino, usuario=None, motivo=""):
    """
    Retorna o documento para qualquer etapa válida do workflow S7.
    Corrigida para usar MAPA_ETAPAS corretamente e não falhar na validação.
    """

    from apps.documentos.views import registrar_workflow

    # Normalizar nome da etapa destino (mapear variações antigas)
    etapa_destino_normalizada = self.MAPA_ETAPAS.get(etapa_destino, etapa_destino)

    # Lista oficial de etapas válidas
    etapas_validas = dict(WORKFLOW_ESTADOS).keys()

    # Se a etapa ao final do mapeamento não pertence ao fluxo, bloquear
    if etapa_destino_normalizada not in etapas_validas:
        return False

    etapa_anterior = self.etapa_atual
    self.etapa_atual = etapa_destino_normalizada
    self.save(update_fields=["etapa_atual"])

    # LOG
    registrar_workflow(
        documento=self,
        etapa=etapa_destino_normalizada,
        status="Retornado",
        request=None,
        observacao=f"{etapa_anterior} → {etapa_destino_normalizada}. Motivo: {motivo or 'Não informado'}"
    )

    return etapa_destino_normalizada

    # ======================================================================
    # 🔄 MÉTODOS DE WORKFLOW (Passo 2)
    # ======================================================================

def enviar_para_proxima_etapa(self, usuario=None):
    """
    Avança automaticamente o documento para a próxima etapa,
    mesmo se o banco tiver nomes antigos/irregulares.
    """

    # 🟧 1. Normalizar etapa atual
    etapa_normalizada = MAPA_ETAPAS.get(self.etapa_atual, self.etapa_atual)

    fluxo = [
        "ELABORACAO",
        "REVISAO_INTERNA",
        "APROVACAO_TECNICA",
        "DOC_CONTROL",
        "ENVIADO_CLIENTE",
        "APROVACAO_CLIENTE",
        "EMISSAO_FINAL",
    ]

    if etapa_normalizada not in fluxo:
        return False

    idx = fluxo.index(etapa_normalizada)

    # última etapa → não avança
    if idx == len(fluxo) - 1:
        return False

    nova_etapa = fluxo[idx + 1]

    # Atualiza no banco no formato novo
    self.etapa_atual = nova_etapa
    self.save(update_fields=["etapa_atual"])

    registrar_log(
        usuario,
        self,
        acao="AVANCAR_ETAPA",
        descricao=f"{etapa_normalizada} → {nova_etapa}",
    )

    return nova_etapa


def retornar_etapa(self, etapa_destino, usuario=None, motivo=""):
    etapa_destino = MAPA_ETAPAS.get(etapa_destino, etapa_destino)

    etapas_validas = dict(WORKFLOW_ESTADOS).keys()

    if etapa_destino not in etapas_validas:
        return False

    etapa_anterior = self.etapa_atual
    self.etapa_atual = etapa_destino
    self.save(update_fields=["etapa_atual"])

    registrar_log(
        usuario,
        self,
        acao="RETORNAR_ETAPA",
        descricao=f"{etapa_anterior} → {etapa_destino}. Motivo: {motivo}",
    )

    return etapa_destino

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
        default="REVISAO"
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
# 🔁 WORKFLOW
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
        default="revisar"
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
# ======================================================================
# 📌 Função utilitária para registrar log no GED
# ======================================================================
def registrar_log(usuario, documento, acao, descricao=None):
    """
    Registro centralizado de ações para auditoria do GED.
    """
    LogAuditoria.objects.create(
        usuario=usuario,
        documento=documento,
        acao=acao,
        descricao=descricao
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
