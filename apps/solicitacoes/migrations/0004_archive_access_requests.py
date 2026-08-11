from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):
    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
        ("solicitacoes", "0003_access_profile_and_project"),
    ]
    operations = [
        migrations.AddField(model_name="solicitaracesso", name="arquivada", field=models.BooleanField(default=False, verbose_name="Arquivada")),
        migrations.AddField(model_name="solicitaracesso", name="data_arquivamento", field=models.DateTimeField(blank=True, null=True, verbose_name="Data do arquivamento")),
        migrations.AddField(model_name="solicitaracesso", name="arquivada_por", field=models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name="solicitacoes_arquivadas", to=settings.AUTH_USER_MODEL, verbose_name="Arquivada por")),
    ]
