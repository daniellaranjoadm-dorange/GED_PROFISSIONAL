from django.contrib.auth.models import AbstractUser
from django.db import models
from django.contrib.auth import get_user_model


# ======================================================================
# 👤 USUÁRIO PERSONALIZADO (AUTH_USER_MODEL)
# ======================================================================
class Usuario(AbstractUser):
    """
    Usuário personalizado do GED com papéis por função.
    MASTER = is_superuser OU is_master.
    """

    is_master = models.BooleanField("Administrador Master", default=False)
    is_engenheiro = models.BooleanField("Engenheiro", default=False)
    is_revisor = models.BooleanField("Revisor", default=False)
    is_aprovador = models.BooleanField("Aprovador", default=False)

    def __str__(self):
        return self.username


# ======================================================================
# ⚙ CONFIGURAÇÕES POR USUÁRIO
# ======================================================================
class UserConfig(models.Model):
    user = models.OneToOneField(Usuario, on_delete=models.CASCADE)

    tema = models.CharField(max_length=20, default="neon")
    animacoes = models.BooleanField(default=True)
    notificacoes_email = models.BooleanField(default=True)
    dashboard_expandido = models.BooleanField(default=True)

    def __str__(self):
        return f"Configurações de {self.user.username}"


# ======================================================================
# 🔐 RBAC – PAPÉIS E VÍNCULOS
# ======================================================================

from django.conf import settings  # <-- TROQUEI get_user_model POR ISTO


class Role(models.Model):
    nome = models.CharField(max_length=50, unique=True)
    descricao = models.TextField(blank=True)

    def __str__(self):
        return self.nome


class UserRole(models.Model):
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)
    role = models.ForeignKey(Role, on_delete=models.CASCADE)

    class Meta:
        unique_together = ("user", "role")

    def __str__(self):
        return f"{self.user.username} -> {self.role.nome}"


# ======================================================================
# PERMISSÕES POR PAPEL (RBAC)
# ======================================================================
class RolePermission(models.Model):
    role = models.ForeignKey(Role, on_delete=models.CASCADE, related_name="permissoes")
    codigo = models.CharField(max_length=100)  # Ex: documentos.criar, documentos.aprovar
    descricao = models.CharField(max_length=200, blank=True)

    class Meta:
        unique_together = ("role", "codigo")

    def __str__(self):
        return f"{self.role.nome} → {self.codigo}"


# ======================================================================
# 📨 SOLICITAÇÃO DE ACESSO AO SISTEMA (NOVO)
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

    def __str__(self):
        return f"{self.nome} ({self.email})"
