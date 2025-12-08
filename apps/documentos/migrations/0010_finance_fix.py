from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('documentos', '0009_alter_arquivodocumento_options_and_more'),
    ]

    operations = [
        # --- Campos Financeiros no Documento ---
        migrations.AddField(
            model_name='documento',
            name='valor_brl',
            field=models.DecimalField(
                null=True, blank=True, max_digits=15, decimal_places=2, verbose_name='Valor (BRL)'
            ),
        ),
        migrations.AddField(
            model_name='documento',
            name='valor_usd',
            field=models.DecimalField(
                null=True, blank=True, max_digits=15, decimal_places=2, verbose_name='Valor (USD)'
            ),
        ),

        # --- Criação do Modelo Financeiro ---
        migrations.CreateModel(
            name='ProjetoFinanceiro',
            fields=[
                ('id', models.AutoField(primary_key=True, serialize=False)),
                ('fase', models.CharField(max_length=50)),
                ('valor_total_usd', models.DecimalField(max_digits=15, decimal_places=2)),
                ('descricao', models.CharField(max_length=255, null=True, blank=True)),
                ('moeda', models.CharField(max_length=10, default='USD')),
                ('projeto', models.ForeignKey(on_delete=models.CASCADE, related_name='financeiro', to='documentos.projeto')),
            ],
        ),
    ]
