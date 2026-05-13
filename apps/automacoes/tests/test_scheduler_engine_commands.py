from io import StringIO

from django.core.management import call_command
from django.test import TestCase

from apps.automacoes.services.scheduler import limpar_registry_jobs_agendados


class SchedulerEngineCommandTests(TestCase):
    def tearDown(self):
        limpar_registry_jobs_agendados()

    def test_init_scheduler_states_command(self):
        output = StringIO()

        call_command("init_scheduler_states", stdout=output)

        self.assertIn("Scheduler states inicializados", output.getvalue())

    def test_scheduler_tick_command(self):
        output = StringIO()

        call_command("scheduler_tick", "--limit", "2", stdout=output)

        self.assertIn("Scheduler tick executado", output.getvalue())
