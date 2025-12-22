import os
from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand

class Command(BaseCommand):
    help = "Garante que exista um superusuário a partir das variáveis de ambiente."

    def handle(self, *args, **options):
        User = get_user_model()

        username_env = os.environ.get("DJANGO_SUPERUSER_USERNAME", "").strip()
        email = os.environ.get("DJANGO_SUPERUSER_EMAIL", "").strip()
        password = os.environ.get("DJANGO_SUPERUSER_PASSWORD", "")
        reset_pw = os.environ.get("DJANGO_SUPERUSER_RESET_PASSWORD", "false").lower() == "true"

        # Identificador usado no login do Django (USERNAME_FIELD)
        identifier = username_env or email
        if not identifier or not password:
            self.stdout.write(self.style.WARNING("Variáveis de superuser ausentes. Pulando."))
            return

        lookup = {User.USERNAME_FIELD: identifier}
        defaults = {}
        if hasattr(User, "email") and email:
            defaults["email"] = email

        user, created = User.objects.get_or_create(**lookup, defaults=defaults)

        # garante permissões de admin
        user.is_staff = True
        user.is_superuser = True
        user.is_active = True

        # atualiza email se existir
        if hasattr(user, "email") and email and user.email != email:
            user.email = email

        if created or reset_pw:
            user.set_password(password)

        user.save()

        self.stdout.write(self.style.SUCCESS(f"Superuser OK: {User.USERNAME_FIELD}={identifier}"))
