from django.utils.functional import SimpleLazyObject
from django.shortcuts import redirect
from django.contrib import messages

from .models import UserRole, RolePermission
from .permissions import usuario_tem_permissao


def _get_user_perms(user):
    """
    Retorna um set() de códigos de permissão do usuário (RBAC).
    MASTER (is_superuser ou is_master) recebe '*'.
    """
    if not user.is_authenticated:
        return set()

    # MASTER sempre tem tudo
    if user.is_superuser or getattr(user, "is_master", False):
        return {"*"}

    # Papeis do usuário
    papeis_ids = UserRole.objects.filter(user=user).values_list("role_id", flat=True)

    if not papeis_ids:
        return set()

    # Permissões dos papéis
    perms = RolePermission.objects.filter(role_id__in=papeis_ids) \
                                  .values_list("codigo", flat=True)

    return set(perms)


class RBACMiddleware:
    """
    Middleware que:
      - monta request.rbac_perms (set de permissões)
      - expõe request.has_rbac_perm(codigo)
    Não substitui seus decorators, apenas facilita uso em views/templates.
    """

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):

        # Lazy: só consulta no banco na primeira vez que usar
        request.rbac_perms = SimpleLazyObject(
            lambda: _get_user_perms(request.user)
        )

        def has_rbac_perm(codigo_perm: str) -> bool:
            """
            Uso em view Python:
                if request.has_rbac_perm("documento.aprovar"):
                    ...
            """
            user = request.user

            if not user.is_authenticated:
                return False

            # MASTER
            if user.is_superuser or getattr(user, "is_master", False):
                return True

            perms = request.rbac_perms  # já é um set ou SimpleLazyObject de set
            return ("*" in perms) or (codigo_perm in perms)

        # Disponível em qualquer view
        request.has_rbac_perm = has_rbac_perm

        response = self.get_response(request)
        return response
