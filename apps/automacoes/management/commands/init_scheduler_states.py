from django.core.management.base import BaseCommand

from apps.automacoes.services.scheduler_engine import inicializar_scheduler_states


class Command(BaseCommand):
    help = "Inicializa estados persistentes dos jobs padrão do Scheduler GED."

    def handle(self, *args, **options):
        states = inicializar_scheduler_states()

        self.stdout.write(
            self.style.SUCCESS(
                f"Scheduler states inicializados: {len(states)}"
            )
        )

        for state in states:
            self.stdout.write(
                f"{state.job_name} | enabled={state.enabled} | next_run_at={state.next_run_at}"
            )
