from django.db import migrations


ROLE_NAME = "ARQUIVO_TECNICO"
ROLE_DESCRIPTION = (
    "Cadastro, organização, consulta e distribuição controlada do acervo técnico."
)
PERMISSIONS = (
    "ged.visualizar",
    "documento.criar",
    "documento.editar",
    "copias.visualizar",
    "copias.operar",
    "ld_pcf.visualizar",
    "km.visualizar",
)


def seed_arquivo_tecnico(apps, schema_editor):
    Role = apps.get_model("contas", "Role")
    RolePermission = apps.get_model("contas", "RolePermission")

    role, _ = Role.objects.update_or_create(
        nome=ROLE_NAME,
        defaults={"descricao": ROLE_DESCRIPTION},
    )
    for codigo in PERMISSIONS:
        RolePermission.objects.get_or_create(
            role=role,
            codigo=codigo,
            defaults={"descricao": codigo.replace(".", " ").title()},
        )


def remove_arquivo_tecnico(apps, schema_editor):
    Role = apps.get_model("contas", "Role")
    Role.objects.filter(nome=ROLE_NAME).delete()


class Migration(migrations.Migration):
    dependencies = [("contas", "0004_seed_controlled_copy_permissions")]
    operations = [
        migrations.RunPython(seed_arquivo_tecnico, remove_arquivo_tecnico),
    ]
