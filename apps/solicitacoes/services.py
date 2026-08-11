from django.conf import settings
from django.contrib.auth import get_user_model
from django.core.mail import send_mail

from apps.contas.models import Role, UserConfig, UserRole
from .models import AuditoriaSolicitacao, SolicitarAcesso


def _get_admin_emails():
    return [getattr(settings, "EMAIL_HOST_USER", settings.DEFAULT_FROM_EMAIL)]


def criar_usuario_para_solicitacao(instancia: SolicitarAcesso, role: Role):
    """Cria uma conta inativa e sem senha até a aceitação do convite."""
    User = get_user_model()
    email = (instancia.email or "").strip().lower()
    nome = (instancia.nome or "").strip()
    if not email:
        return None, False

    usuario, created = User.objects.get_or_create(
        email=email,
        defaults={"username": email, "first_name": nome, "is_active": False},
    )
    if created:
        usuario.set_unusable_password()
        usuario.save(update_fields=["password"])
    else:
        usuario.is_active = False
        usuario.set_unusable_password()
        usuario.save(update_fields=["is_active", "password"])

    UserConfig.objects.get_or_create(user=usuario)
    UserRole.objects.filter(user=usuario).exclude(role__nome="MASTER").delete()
    UserRole.objects.get_or_create(user=usuario, role=role)
    return usuario, created


def registrar_auditoria_solicitacao(
    instancia, usuario_responsavel=None, status_anterior=None, status_novo=None,
    ip=None, observacao="", usuario_criado=None,
):
    AuditoriaSolicitacao.objects.create(
        solicitacao=instancia, usuario_responsavel=usuario_responsavel,
        usuario_criado=usuario_criado, status_anterior=status_anterior or "",
        status_novo=status_novo or "", ip=ip, observacao=observacao or "",
    )


def notificar_nova_solicitacao(instancia):
    send_mail(
        subject="[GED] Nova solicitação de acesso",
        message=(
            "Uma nova solicitação de acesso foi registrada no GED.\n\n"
            f"Nome: {instancia.nome}\nE-mail: {instancia.email}\n"
            f"Setor: {instancia.setor or '-'}\nProjeto: {instancia.projeto_empresa or '-'}\n"
            f"Perfil solicitado: {instancia.perfil_solicitado or '-'}\n\n"
            f"Motivo:\n{instancia.motivo}\n"
        ),
        from_email=settings.DEFAULT_FROM_EMAIL,
        recipient_list=_get_admin_emails(), fail_silently=True,
    )


def notificar_decisao_solicitacao(instancia, convite_url=None):
    if not instancia.email:
        return
    status_msg = instancia.get_status_display().upper()
    mensagem = (
        f"Olá, {instancia.nome}.\n\nSua solicitação de acesso ao GED foi analisada.\n\n"
        f"Status: {status_msg}\nPerfil concedido: {instancia.perfil_concedido or '-'}\n"
    )
    if instancia.observacao_admin:
        mensagem += f"\nObservação do responsável:\n{instancia.observacao_admin}\n"
    if convite_url and instancia.status == SolicitarAcesso.STATUS_APROVADO:
        mensagem += (
            "\nCrie sua senha pessoal pelo link seguro abaixo:\n"
            f"Usuário (login): {instancia.email}\n{convite_url}\n"
            "\nO link é individual, possui validade limitada e nenhuma senha é enviada por e-mail.\n"
        )
    send_mail(
        subject="[GED] Decisão sobre sua solicitação de acesso",
        message=mensagem, from_email=settings.DEFAULT_FROM_EMAIL,
        recipient_list=[instancia.email], fail_silently=True,
    )
