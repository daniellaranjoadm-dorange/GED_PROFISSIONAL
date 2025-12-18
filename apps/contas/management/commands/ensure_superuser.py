import os
from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand


class Command(BaseCommand):
    help = "Garante que exista um superusuário a partir das variáveis de ambiente."

    def handle(self, *args, **options):
        username = os.environ.get("DJANGO_SUPERUSER_USERNAME")
        email = os.environ.get("DJANGO_SUPERUSER_EMAIL", "")
        password = os.environ.get("DJANGO_SUPERUSER_PASSWORD")
        reset_pw = os.environ.get("DJANGO_SUPERUSER_RESET_PASSWORD", "false").lower() == "true"

        if not username or not password:
            self.stdout.write(self.style.WARNING(
                "ensure_superuser: variáveis DJANGO_SUPERUSER_USERNAME e/ou DJANGO_SUPERUSER_PASSWORD não definidas. Ignorando."
            ))
            return

        User = get_user_model()
        user, created = User.objects.get_or_create(
            username=username,
            defaults={
                "email": email,
                "is_staff": True,
                "is_superuser": True,
            },
        )

        changed = False

        if not user.is_staff:
            user.is_staff = True
            changed = True
        if not user.is_superuser:
            user.is_superuser = True
            changed = True

        if email and user.email != email:
            user.email = email
            changed = True

        # Segurança: só reseta senha se você pedir explicitamente
        if created or reset_pw:
            user.set_password(password)
            changed = True

        if changed:
            user.save()

        if created:
            self.stdout.write(self.style.SUCCESS(f"Superusuário criado: {username}"))
        else:
            self.stdout.write(self.style.SUCCESS(f"Superusuário verificado/ajustado: {username}"))
