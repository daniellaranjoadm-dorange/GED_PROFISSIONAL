from django.db import models
from django.contrib.auth.models import AbstractUser
from django.conf import settings


# ======================================================================
# 👤 USUÁRIO PRINCIPAL DO SISTEMA (AUTH_USER_MODEL)
# ======================================================================
class Usuario(AbstractUser):
    """
    Modelo base do usuário do GED:
    - Pode ser usado como RBAC puro sem depender do Django Groups
    - Flags extras ajudam a diferenciar perfis
    """

    is_master = models.BooleanField("Administrador Master", default=False)
    is_engenheiro = models.BooleanField("Engenheiro", default=False)
    is_revisor = models.BooleanField("Revisor", default=False)
    is_aprovador = models.BooleanField("Aprovador", default=False)

    class Meta:
        verbose_name = "Usuário"
        verbose_name_plural = "Usuários"

    def __str__(self):
        return self.username


# ======================================================================
# ⚙ CONFIGURAÇÕES INDIVIDUAIS DO USUÁRIO
# ======================================================================
class UserConfig(models.Model):
    user = models.OneToOneField(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)

    tema = models.CharField(max_length=20, default="neon")     # neon / light / dark...
    animacoes = models.BooleanField(default=True)
    notificacoes_email = models.BooleanField(default=True)
    dashboard_expandido = models.BooleanField(default=True)

    class Meta:
        verbose_name = "Configuração do Usuário"
        verbose_name_plural = "Configurações dos Usuários"

    def __str__(self):
        return f"Configurações → {self.user.username}"


# ======================================================================
# 🔐 RBAC — PAPÉIS E PERMISSÕES AVANÇADAS
# ======================================================================
class Role(models.Model):
    nome = models.CharField(max_length=50, unique=True)
    descricao = models.TextField(blank=True)

    class Meta:
        verbose_name = "Papel"
        verbose_name_plural = "Papéis"

    def __str__(self):
        return self.nome


class UserRole(models.Model):
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)
    role = models.ForeignKey(Role, on_delete=models.CASCADE)

    class Meta:
        unique_together = ("user", "role")
        verbose_name = "Vínculo Usuário → Papel"
        verbose_name_plural = "Vínculos Usuários → Papéis"

    def __str__(self):
        return f"{self.user.username} → {self.role.nome}"


class RolePermission(models.Model):
    role = models.ForeignKey(Role, on_delete=models.CASCADE, related_name="permissoes")
    codigo = models.CharField(max_length=100)  # Ex: documentos.criar, workflow.aprovar
    descricao = models.CharField(max_length=200, blank=True)

    class Meta:
        unique_together = ("role", "codigo")
        verbose_name = "Permissão de Papel"
        verbose_name_plural = "Permissões de Papéis"

    def __str__(self):
        return f"{self.role.nome} → {self.codigo}"


# ======================================================================
# 📨 SOLICITAÇÕES DE ACESSO AO SISTEMA
# ======================================================================
class SolicitacaoAcesso(models.Model):
    nome = models.CharField(max_length=150)
    email = models.EmailField()
    departamento = models.CharField(max_length=150, blank=True)
    mensagem = models.TextField(blank=True)
    data = models.DateTimeField(auto_now_add=True)

    STATUS_CHOICES = [
        ("pendente", "Pendente"),
        ("aprovado", "Aprovado"),
        ("negado", "Negado"),
    ]

    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default="pendente")

    class Meta:
        verbose_name = "Solicitação de Acesso"
        verbose_name_plural = "Solicitações de Acesso"

    def __str__(self):
        return f"{self.nome} ({self.email})"
