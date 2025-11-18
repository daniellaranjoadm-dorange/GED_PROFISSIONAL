from django.contrib.auth.models import AbstractUser
from django.db import models


class Usuario(AbstractUser):
    """
    UsuÃ¡rio personalizado do GED com papÃ©is por funÃ§Ã£o.
    MASTER = is_superuser OU is_master.
    """

    # PAPEIS
    is_master = models.BooleanField("Administrador Master", default=False)
    is_engenheiro = models.BooleanField("Engenheiro", default=False)
    is_revisor = models.BooleanField("Revisor", default=False)
    is_aprovador = models.BooleanField("Aprovador", default=False)

    # (se quiser no futuro podemos adicionar: is_planejador, is_documentalista, etc.)

    def __str__(self):
        return self.username

