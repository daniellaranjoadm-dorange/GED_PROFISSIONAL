from django.core.management.base import BaseCommand

from apps.automacoes.services.health_jobs import registrar_health_jobs
from apps.automacoes.services.km_scheduler_jobs import registrar_km_jobs
from apps.automacoes.services.scheduler import listar_jobs_agendados


class Command(BaseCommand):
    help = "Lista jobs agendados do GED."

    def handle(self, *args, **options):
        registrar_health_jobs()
        registrar_km_jobs()

        jobs = list(listar_jobs_agendados(include_disabled=True))

        if not jobs:
            self.stdout.write("Nenhum job registrado.")
            return

        self.stdout.write("")
        self.stdout.write(self.style.SUCCESS("Jobs agendados do GED"))
        self.stdout.write("-" * 60)

        for job in jobs:
            status = "ENABLED" if job.enabled else "DISABLED"

            self.stdout.write(
                f"{job.name:<25} {status:<10} {job.description}"
            )

        self.stdout.write("-" * 60)
        self.stdout.write(f"Total: {len(jobs)}")
