from django.test import TestCase

from apps.automacoes.models import JobExecution
from apps.automacoes.services.health_jobs import executar_health_scan, registrar_health_jobs
from apps.automacoes.services.scheduler import executar_job_agendado, limpar_registry_jobs_agendados


class HealthJobsTests(TestCase):
    def tearDown(self):
        limpar_registry_jobs_agendados()

    def test_executar_health_scan_retorna_metricas(self):
        resultado = executar_health_scan()

        self.assertTrue(resultado["ok"])
        self.assertIn("metricas", resultado)
        self.assertIn("documentos_ld", resultado["metricas"])

    def test_health_scan_como_job_agendado(self):
        registrar_health_jobs()

        job = executar_job_agendado("health_scan")

        self.assertEqual(job.status, JobExecution.STATUS_SUCCESS)
        self.assertTrue(job.result.get("ok"))
        self.assertIn("metricas", job.result)
