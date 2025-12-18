from django.core.management.base import BaseCommand
from django.contrib.auth.models import Group


class Command(BaseCommand):
    help = "Cria / atualiza grupos padrão do Workflow Enterprise Naval"

    DISCIPLINAS = [
        "NAV",   # Naval
        "TUB",   # Tubulação
        "MEC",   # Mecânica
        "ELE",   # Elétrica
        "AUT",   # Automação
        "CIV",   # Civil
        "PROC",  # Processos
        "HSE",   # Segurança / Meio ambiente
        "DC",   # Doc Control
    ]

    GRUPOS_FIXOS = [
        "DOC_CONTROL",
        "DOC_CONTROL_PCF",
        "CLIENTE",
        "MASTER_ADMIN",   # Opcional, mas recomendado
    ]

    def handle(self, *args, **kwargs):
        self.stdout.write("\n🔧 Criando grupos do Workflow Enterprise Naval...\n")

        # ==============================
        # 1) Grupos por disciplina
        # ==============================
        for d in self.DISCIPLINAS:
            nome_rev = f"REVISORES_{d}"
            nome_coord = f"COORD_{d}"

            Group.objects.get_or_create(name=nome_rev)
            self.stdout.write(self.style.SUCCESS(f"✓ Grupo criado/atualizado: {nome_rev}"))

            Group.objects.get_or_create(name=nome_coord)
            self.stdout.write(self.style.SUCCESS(f"✓ Grupo criado/atualizado: {nome_coord}"))

        # ==============================
        # 2) Grupos fixos do workflow
        # ==============================
        for g in self.GRUPOS_FIXOS:
            Group.objects.get_or_create(name=g)
            self.stdout.write(self.style.SUCCESS(f"✓ Grupo criado/atualizado: {g}"))

        # ==============================
        # Finalização
        # ==============================
        self.stdout.write("\n🚀 Todos os grupos do workflow foram configurados com sucesso!\n")

