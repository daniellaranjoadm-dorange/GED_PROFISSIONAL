from django.db import migrations


def seed_operational_rbac(apps, schema_editor):
    Role = apps.get_model("contas", "Role")
    RolePermission = apps.get_model("contas", "RolePermission")
    from apps.contas.rbac_catalog import PERMISSOES_POR_PAPEL, ROLES_PADRAO

    roles = {}
    for nome, descricao in ROLES_PADRAO.items():
        role, _ = Role.objects.update_or_create(nome=nome, defaults={"descricao": descricao})
        roles[nome] = role
    for role_nome, codigos in PERMISSOES_POR_PAPEL.items():
        for codigo in codigos:
            RolePermission.objects.get_or_create(
                role=roles[role_nome], codigo=codigo,
                defaults={"descricao": codigo.replace(".", " ").title()},
            )


class Migration(migrations.Migration):
    dependencies = [("contas", "0002_alter_role_options_alter_rolepermission_options_and_more")]
    operations = [migrations.RunPython(seed_operational_rbac, migrations.RunPython.noop)]
