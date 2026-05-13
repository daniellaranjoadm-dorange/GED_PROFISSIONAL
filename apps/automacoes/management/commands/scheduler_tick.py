from django.core.management.base import BaseCommand

from apps.automacoes.services.scheduler_engine import scheduler_tick


class Command(BaseCommand):
    help = "Executa um ciclo controlado do Scheduler GED."

    def add_arguments(self, parser):
        parser.add_argument(
            "--limit",
            type=int,
            default=10,
            help="Quantidade máxima de jobs vencidos a executar neste ciclo.",
        )

    def handle(self, *args, **options):
        resultado = scheduler_tick(limit=options["limit"])

        self.stdout.write(self.style.SUCCESS("Scheduler tick executado."))
        self.stdout.write(f"Executados: {resultado['total_executados']}")
        self.stdout.write(f"Ignorados: {resultado['total_ignorados']}")
        self.stdout.write(f"Erros: {resultado['total_erros']}")

        if resultado["erros"]:
            for erro in resultado["erros"]:
                self.stdout.write(
                    self.style.ERROR(
                        f"{erro.get('job_name')}: {erro.get('erro')}"
                    )
                )
