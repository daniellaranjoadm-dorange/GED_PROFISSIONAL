from django.db import migrations


def seed_permissions(apps, schema_editor):
    Role = apps.get_model("contas", "Role")
    RolePermission = apps.get_model("contas", "RolePermission")
    matrix = {
        "MASTER": ["copias.visualizar", "copias.operar"],
        "GESTOR": ["copias.visualizar"],
        "DOCUMENT_CONTROL": ["copias.visualizar", "copias.operar"],
        "APROVADOR": ["copias.visualizar"],
        "CONSULTA": ["copias.visualizar"],
    }
    for role_name, codes in matrix.items():
        role = Role.objects.filter(nome=role_name).first()
        if not role:
            continue
        for code in codes:
            RolePermission.objects.get_or_create(
                role=role, codigo=code,
                defaults={"descricao": code.replace(".", " ").title()},
            )


class Migration(migrations.Migration):
    dependencies = [("contas", "0003_seed_operational_rbac")]
    operations = [migrations.RunPython(seed_permissions, migrations.RunPython.noop)]
