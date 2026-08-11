from django.db.models.signals import post_migrate
from django.dispatch import receiver

from .models import Role, RolePermission
from .rbac_catalog import PERMISSOES_POR_PAPEL, ROLES_PADRAO


@receiver(post_migrate)
def criar_roles_e_permissoes(sender, **kwargs):
    if sender.label != "contas":
        return

    roles = {}
    for nome, descricao in ROLES_PADRAO.items():
        role, _ = Role.objects.update_or_create(nome=nome, defaults={"descricao": descricao})
        roles[nome] = role

    for role_nome, codigos in PERMISSOES_POR_PAPEL.items():
        for codigo in codigos:
            RolePermission.objects.get_or_create(
                role=roles[role_nome],
                codigo=codigo,
                defaults={"descricao": codigo.replace(".", " ").title()},
            )
