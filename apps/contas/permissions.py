from functools import wraps
from django.shortcuts import redirect
from django.contrib import messages
from django.contrib.auth.decorators import login_required

# ❌ REMOVIDO: from apps.contas.permissions import usuario_tem_permissao
# (isso causava circular import e travava o servidor)

from apps.contas.models import UserRole, RolePermission


def usuario_tem_permissao(usuario, codigo_perm):
    """
    Retorna True se o usuário tiver a permissão pelo RBAC.
    """
    if usuario.is_superuser or getattr(usuario, "is_master", False):
        return True

    papeis = UserRole.objects.filter(user=usuario).values_list("role_id", flat=True)
    if not papeis:
        return False

    permissoes = RolePermission.objects.filter(role_id__in=papeis).values_list(
        "codigo", flat=True
    )

    return codigo_perm in permissoes


def rota_inicial_usuario(usuario):
    """Retorna uma tela inicial que o perfil realmente pode acessar."""
    if usuario_tem_permissao(usuario, "automacoes.visualizar"):
        return "automacoes:painel"
    if usuario_tem_permissao(usuario, "ged.visualizar"):
        return "documentos:listar_documentos"
    if usuario_tem_permissao(usuario, "copias.operar"):
        return "carimbos:guias"
    if usuario_tem_permissao(usuario, "copias.visualizar"):
        return "carimbos:rastreabilidade"
    return "contas:minhas_configuracoes"


def has_perm(codigo):
    """
    Decorador: @has_perm("documento.aprovar")
    """
    def decorator(view_func):
        @wraps(view_func)
        @login_required
        def wrapper(request, *args, **kwargs):
            if usuario_tem_permissao(request.user, codigo):
                return view_func(request, *args, **kwargs)

            messages.error(request, "Você não tem permissão para acessar esta função.")
            return redirect(rota_inicial_usuario(request.user))

        return wrapper

    return decorator
