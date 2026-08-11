from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [("automacoes", "0022_documentold_action_documentold_casco_and_more")]
    operations = [
        migrations.AddField(
            model_name="execucaoautomacao",
            name="origem",
            field=models.CharField(db_index=True, default="painel", max_length=30),
        ),
        migrations.AddField(
            model_name="execucaoautomacao",
            name="arquivo_origem",
            field=models.TextField(blank=True),
        ),
        migrations.AddField(
            model_name="execucaoautomacao",
            name="ip_origem",
            field=models.GenericIPAddressField(blank=True, null=True),
        ),
    ]
