from django.core.mail import send_mail
from django.conf import settings
from django.contrib.auth import get_user_model
from django.contrib.auth.models import Group
from django.utils.crypto import get_random_string

from .models import SolicitarAcesso, AuditoriaSolicitacao
from apps.contas.models import Role, UserRole, UserConfig



# ============================================================
# E-MAIL PARA ADMINISTRADORES
# ============================================================
def _get_admin_emails() -> list[str]:
    return [getattr(settings, "EMAIL_HOST_USER", settings.DEFAULT_FROM_EMAIL)]


# ============================================================
# RBAC AUTOMÁTICO
# ============================================================
def _garantir_role_usuario_ged():
    """Garante que a Role 'Usuário GED' exista."""
    role, created = Role.objects.get_or_create(
        nome="Usuário GED",
        defaults={"descricao": "Acesso padrão ao GED"},
    )
    return role


def _garantir_group_usuario_ged():
    """Cria ou obtém o grupo Django 'usuario_ged'."""
    group, created = Group.objects.get_or_create(name="usuario_ged")
    # Aqui podemos adicionar permissões no futuro
    return group


def criar_usuario_para_solicitacao(instancia: SolicitarAcesso):
    """
    Cria usuário automaticamente ao aprovar solicitação.
    - Username = e-mail
    - Cria Role 'Usuário GED'
    - Adiciona ao Group Django 'usuario_ged'
    - Gera senha temporária se for novo usuário
    """
    User = get_user_model()

    email = (instancia.email or "").strip().lower()
    nome = (instancia.nome or "").strip()

    if not email:
        return None, None, False

    usuario, created = User.objects.get_or_create(
        email=email,
        defaults={
            "username": email,
            "first_name": nome,
            "is_active": True,
        },
    )

    senha_temporaria = None

    if created:
        senha_temporaria = get_random_string(12)
        usuario.set_password(senha_temporaria)
        usuario.save()

    # Garante UserConfig
    UserConfig.objects.get_or_create(user=usuario)

    # ============================================================
    # Role → Banco de Dados
    # ============================================================
    role = _garantir_role_usuario_ged()
    UserRole.objects.get_or_create(user=usuario, role=role)

    # ============================================================
    # Group → Django Admin
    # ============================================================
    group = _garantir_group_usuario_ged()
    usuario.groups.add(group)

    return usuario, senha_temporaria, created


# ============================================================
# AUDITORIA
# ============================================================
def registrar_auditoria_solicitacao(
    instancia: SolicitarAcesso,
    usuario_responsavel=None,
    status_anterior: str | None = None,
    status_novo: str | None = None,
    ip: str | None = None,
    observacao: str = "",
    usuario_criado=None,
) -> None:
    """Registra um evento de auditoria para a solicitação."""
    AuditoriaSolicitacao.objects.create(
        solicitacao=instancia,
        usuario_responsavel=usuario_responsavel,
        usuario_criado=usuario_criado,
        status_anterior=status_anterior or "",
        status_novo=status_novo or "",
        ip=ip,
        observacao=observacao or "",
    )


# ============================================================
# NOTIFICAÇÕES
# ============================================================
def notificar_nova_solicitacao(instancia: SolicitarAcesso) -> None:
    assunto = "[GED] Nova solicitação de acesso"
    mensagem = (
        "Uma nova solicitação de acesso foi registrada no GED.\n\n"
        f"Nome: {instancia.nome}\n"
        f"E-mail: {instancia.email}\n"
        f"Setor: {instancia.setor or '-'}\n"
        f"Status: {instancia.get_status_display()}\n\n"
        f"Motivo:\n{instancia.motivo}\n"
    )

    send_mail(
        subject=assunto,
        message=mensagem,
        from_email=settings.DEFAULT_FROM_EMAIL,
        recipient_list=_get_admin_emails(),
        fail_silently=True,
    )


def notificar_decisao_solicitacao(
    instancia: SolicitarAcesso,
    senha_temporaria: str | None = None,
) -> None:
    if not instancia.email:
        return

    assunto = "[GED] Decisão sobre sua solicitação de acesso"

    if instancia.status == SolicitarAcesso.STATUS_APROVADO:
        status_msg = "APROVADA"
    elif instancia.status == SolicitarAcesso.STATUS_NEGADO:
        status_msg = "NEGADA"
    else:
        status_msg = instancia.get_status_display().upper()

    mensagem = (
        f"Olá, {instancia.nome}.\n\n"
        "Sua solicitação de acesso ao GED foi analisada.\n\n"
        f"Status: {status_msg}\n"
    )

    if instancia.observacao_admin:
        mensagem += f"\nObservação do responsável:\n{instancia.observacao_admin}\n"

    # Credenciais se for aprovado e novo
    if senha_temporaria and instancia.status == SolicitarAcesso.STATUS_APROVADO:
        mensagem += (
            "\nSeus dados de acesso ao GED:\n"
            f"Usuário (login): {instancia.email}\n"
            f"Senha temporária: {senha_temporaria}\n"
            "\nPor segurança, altere sua senha no primeiro acesso.\n"
        )

    send_mail(
        subject=assunto,
        message=mensagem,
        from_email=settings.DEFAULT_FROM_EMAIL,
        recipient_list=[instancia.email],
        fail_silently=True,
    )
