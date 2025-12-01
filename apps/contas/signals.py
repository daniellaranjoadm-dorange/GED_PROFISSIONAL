from django.db.models.signals import post_migrate
from django.dispatch import receiver
from .models import Role, RolePermission

@receiver(post_migrate)
def criar_roles_e_permissoes(sender, **kwargs):
    if sender.label != "contas":
        return
    
    # ---------------------------------------------------------
    # CRIAR ROLES PADRÃO
    # ---------------------------------------------------------
    roles_padrao = {
        "MASTER": "Acesso total ao sistema",
        "ENGENHEIRO": "Pode criar e editar documentos",
        "REVISOR": "Pode revisar documentos",
        "APROVADOR": "Pode aprovar documentos",
    }

    roles_obj = {}
    for nome, desc in roles_padrao.items():
        role, _ = Role.objects.get_or_create(nome=nome, defaults={"descricao": desc})
        roles_obj[nome] = role

    # ---------------------------------------------------------
    # PERMISSÕES POR PAPEL
    # ---------------------------------------------------------
    permissoes = {
        "MASTER": [
            "documento.criar",
            "documento.editar",
            "documento.excluir",
            "documento.revisar",
            "documento.aprovar",
            "documento.emitir",
        ],

        "ENGENHEIRO": [
            "documento.criar",
            "documento.editar",
        ],

        "REVISOR": [
            "documento.revisar",
        ],

        "APROVADOR": [
            "documento.aprovar",
            "documento.emitir",
        ],
    }

    # Criar permissões na tabela RolePermission
    for role_nome, lista_perms in permissoes.items():
        role = roles_obj[role_nome]

        for cod in lista_perms:
            RolePermission.objects.get_or_create(
                role=role,
                codigo=cod,
                defaults={"descricao": cod.replace(".", " ").title()}
            )
