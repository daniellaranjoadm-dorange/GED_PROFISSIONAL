from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [("automacoes", "0026_pcftimeline_documento_ged_and_more")]

    operations = [
        migrations.AddField(
            model_name="documentold",
            name="medicao_emissao",
            field=models.CharField(blank=True, db_index=True, max_length=50),
        ),
        migrations.AddField(
            model_name="documentold",
            name="medicao_aprovacao",
            field=models.CharField(blank=True, db_index=True, max_length=50),
        ),
        migrations.AddField(
            model_name="documentold",
            name="cronograma_inicio",
            field=models.CharField(blank=True, max_length=50),
        ),
        migrations.AddField(
            model_name="documentold",
            name="cronograma_termino",
            field=models.CharField(blank=True, max_length=50),
        ),
    ]
