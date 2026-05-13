from django.test import TestCase

from apps.automacoes.models import JobExecution
from apps.automacoes.services.job_analytics import obter_job_analytics


class JobAnalyticsTests(TestCase):
    def test_obter_job_analytics_sem_jobs(self):
        dados = obter_job_analytics()

        self.assertEqual(dados["total"], 0)
        self.assertEqual(dados["taxa_sucesso"], 0)
        self.assertEqual(list(dados["recentes"]), [])

    def test_obter_job_analytics_com_jobs(self):
        JobExecution.objects.create(
            job_name="km_index",
            status=JobExecution.STATUS_SUCCESS,
            duration_ms=1000,
            result={"ok": True},
        )
        JobExecution.objects.create(
            job_name="km_index",
            status=JobExecution.STATUS_FAILED,
            duration_ms=3000,
            result={"ok": False},
            error="falha",
        )
        JobExecution.objects.create(
            job_name="health_scan",
            status=JobExecution.STATUS_RUNNING,
            result={},
        )

        dados = obter_job_analytics()

        self.assertEqual(dados["total"], 3)
        self.assertEqual(dados["total_success"], 1)
        self.assertEqual(dados["total_failed"], 1)
        self.assertEqual(dados["total_running"], 1)
        self.assertEqual(dados["taxa_sucesso"], 50.0)
        self.assertEqual(dados["duracao_media_ms"], 2000)
        self.assertEqual(len(dados["por_job"]), 2)
