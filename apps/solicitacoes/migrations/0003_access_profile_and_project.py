from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):
    dependencies = [
        ("contas", "0003_seed_operational_rbac"),
        ("solicitacoes", "0002_auditoriasolicitacao"),
    ]
    operations = [
        migrations.AddField(
            model_name="solicitaracesso", name="projeto_empresa",
            field=models.CharField(blank=True, max_length=200, verbose_name="Projeto / empresa"),
        ),
        migrations.AddField(
            model_name="solicitaracesso", name="perfil_solicitado",
            field=models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name="solicitacoes_acesso", to="contas.role", verbose_name="Perfil solicitado"),
        ),
        migrations.AddField(
            model_name="solicitaracesso", name="perfil_concedido",
            field=models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name="solicitacoes_aprovadas", to="contas.role", verbose_name="Perfil concedido"),
        ),
    ]
