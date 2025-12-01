from django.core.management.base import BaseCommand
from django.contrib.auth.models import Group

DISCIPLINAS = [
    "NAV", "TUB", "MEC", "ELE",
    "AUT", "CIV", "PROC", "HSE"
]

class Command(BaseCommand):
    help = "Cria os grupos padrão para workflow enterprise"

    def handle(self, *args, **kwargs):

        for d in DISCIPLINAS:
            Group.objects.get_or_create(name=f"REVISORES_{d}")
            Group.objects.get_or_create(name=f"COORD_{d}")
            self.stdout.write(self.style.SUCCESS(f"Grupos criados para {d}"))

        Group.objects.get_or_create(name="CLIENTE")

        self.stdout.write(self.style.SUCCESS("Todos os grupos do workflow foram criados!"))
