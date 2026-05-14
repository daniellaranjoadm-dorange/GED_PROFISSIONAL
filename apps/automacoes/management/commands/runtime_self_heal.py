from django.core.management.base import BaseCommand

from apps.automacoes.services.runtime_healing import executar_self_healing_runtime


class Command(BaseCommand):
    help = "Executa rotinas de self-healing do runtime GED."

    def handle(self, *args, **options):
        resultado = executar_self_healing_runtime()

        self.stdout.write(self.style.SUCCESS("Self-healing runtime executado."))
        self.stdout.write(f"Jobs recuperados: {resultado['jobs_recuperados']}")
        self.stdout.write(f"States recuperados: {resultado['states_recuperados']}")
