from django.db import migrations


ROLE_NAME = "ARQUIVO_TECNICO"
ALLOWED_PERMISSIONS = {"copias.visualizar", "copias.operar"}


def restrict_arquivo_tecnico(apps, schema_editor):
    Role = apps.get_model("contas", "Role")
    RolePermission = apps.get_model("contas", "RolePermission")
    role = Role.objects.filter(nome=ROLE_NAME).first()
    if role is None:
        return

    RolePermission.objects.filter(role=role).exclude(
        codigo__in=ALLOWED_PERMISSIONS
    ).delete()
    for codigo in ALLOWED_PERMISSIONS:
        RolePermission.objects.get_or_create(
            role=role,
            codigo=codigo,
            defaults={"descricao": codigo.replace(".", " ").title()},
        )


class Migration(migrations.Migration):
    dependencies = [("contas", "0005_seed_arquivo_tecnico_role")]
    operations = [migrations.RunPython(restrict_arquivo_tecnico, migrations.RunPython.noop)]
