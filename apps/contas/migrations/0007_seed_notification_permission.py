from django.db import migrations


ROLES = ("MASTER", "GESTOR", "DOCUMENT_CONTROL", "OPERADOR_AUTOMACOES")
PERMISSION = "notificacoes.visualizar"


def seed_notification_permission(apps, schema_editor):
    Role = apps.get_model("contas", "Role")
    RolePermission = apps.get_model("contas", "RolePermission")
    for role in Role.objects.filter(nome__in=ROLES):
        RolePermission.objects.get_or_create(
            role=role,
            codigo=PERMISSION,
            defaults={"descricao": "Visualizar central de notificações"},
        )


class Migration(migrations.Migration):
    dependencies = [("contas", "0006_restrict_arquivo_tecnico_to_controlled_copies")]
    operations = [migrations.RunPython(seed_notification_permission, migrations.RunPython.noop)]
