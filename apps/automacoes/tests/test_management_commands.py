from io import StringIO

from django.core.management import call_command
from django.core.management.base import CommandError
from django.test import TestCase

from apps.automacoes.services.scheduler import limpar_registry_jobs_agendados


class ManagementCommandsTests(TestCase):
    def tearDown(self):
        limpar_registry_jobs_agendados()

    def test_list_scheduled_jobs_command(self):
        output = StringIO()

        call_command(
            "list_scheduled_jobs",
            stdout=output,
        )

        conteudo = output.getvalue()

        self.assertIn("health_scan", conteudo)
        self.assertIn("km_reindex", conteudo)

    def test_run_scheduled_job_command(self):
        output = StringIO()

        call_command(
            "run_scheduled_job",
            "health_scan",
            stdout=output,
        )

        conteudo = output.getvalue()

        self.assertIn("Job executado com sucesso", conteudo)
        self.assertIn("SUCCESS", conteudo)

    def test_run_scheduled_job_inexistente(self):
        with self.assertRaises(CommandError):
            call_command(
                "run_scheduled_job",
                "nao_existe",
            )
