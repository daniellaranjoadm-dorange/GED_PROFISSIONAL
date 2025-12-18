from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ("documentos", "0009_alter_arquivodocumento_options_and_more"),
    ]

    operations = [
        migrations.RunSQL(
            sql="""
            ALTER TABLE documentos_documento
            ADD COLUMN IF NOT EXISTS valor_brl NUMERIC(15,2);

            ALTER TABLE documentos_documento
            ADD COLUMN IF NOT EXISTS valor_usd NUMERIC(15,2);
            """,
            reverse_sql="""
            ALTER TABLE documentos_documento
            DROP COLUMN IF EXISTS valor_brl;

            ALTER TABLE documentos_documento
            DROP COLUMN IF EXISTS valor_usd;
            """,
        ),
    ]
