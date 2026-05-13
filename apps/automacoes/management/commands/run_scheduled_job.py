from django.core.management.base import BaseCommand, CommandError

from apps.automacoes.services.health_jobs import registrar_health_jobs
from apps.automacoes.services.km_scheduler_jobs import registrar_km_jobs
from apps.automacoes.services.scheduler import executar_job_agendado


class Command(BaseCommand):
    help = "Executa um job agendado do GED."

    def add_arguments(self, parser):
        parser.add_argument(
            "job_name",
            type=str,
            help="Nome do job agendado.",
        )

    def handle(self, *args, **options):
        registrar_health_jobs()
        registrar_km_jobs()

        job_name = options["job_name"]

        try:
            job = executar_job_agendado(job_name)
        except ValueError as exc:
            raise CommandError(str(exc))

        self.stdout.write(
            self.style.SUCCESS(
                f"Job executado com sucesso: {job.job_name}"
            )
        )

        self.stdout.write(
            f"Status: {job.status}"
        )

        self.stdout.write(
            f"ID execução: {job.id}"
        )
