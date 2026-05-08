from django.db import models


class ExecucaoAutomacao(models.Model):
    nome = models.CharField(max_length=100)
    status = models.CharField(max_length=30, default="iniciado")
    mensagem = models.TextField(blank=True)
    iniciado_em = models.DateTimeField(auto_now_add=True)
    finalizado_em = models.DateTimeField(null=True, blank=True)

    def __str__(self):
        return f"{self.nome} - {self.status}"


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
        unique_together = ("origem_aba", "documento", "revisao")

    def __str__(self):
        return f"{self.documento} R{self.revisao}"

