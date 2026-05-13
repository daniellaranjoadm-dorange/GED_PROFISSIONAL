from django.db import migrations


def aplicar_finance_fix(apps, schema_editor):
    if schema_editor.connection.vendor == "sqlite":
        return

    schema_editor.execute("""
        ALTER TABLE documentos_documento
        ADD COLUMN IF NOT EXISTS valor_brl NUMERIC(15,2);
    """)

    schema_editor.execute("""
        ALTER TABLE documentos_documento
        ADD COLUMN IF NOT EXISTS valor_usd NUMERIC(15,2);
    """)


def reverter_finance_fix(apps, schema_editor):
    if schema_editor.connection.vendor == "sqlite":
        return

    schema_editor.execute("""
        ALTER TABLE documentos_documento
        DROP COLUMN IF EXISTS valor_brl;
    """)

    schema_editor.execute("""
        ALTER TABLE documentos_documento
        DROP COLUMN IF EXISTS valor_usd;
    """)


class Migration(migrations.Migration):

    dependencies = [
        ("documentos", "0009_alter_arquivodocumento_options_and_more"),
    ]

    operations = [
        migrations.RunPython(
            aplicar_finance_fix,
            reverter_finance_fix,
        ),
    ]