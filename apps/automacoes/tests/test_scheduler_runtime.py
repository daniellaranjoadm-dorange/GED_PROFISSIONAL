from django.test import TestCase
from django.utils import timezone

from apps.automacoes.models import JobExecution
from apps.automacoes.services.scheduler import (
    ScheduledJob,
    limpar_registry_jobs_agendados,
    registrar_job_agendado,
)
from apps.automacoes.services.scheduler_runtime import (
    JobAlreadyRunningError,
    executar_job_agendado_com_lock,
    existe_job_em_execucao,
    marcar_jobs_presos_como_falha,
)


class SchedulerRuntimeTests(TestCase):
    def tearDown(self):
        limpar_registry_jobs_agendados()

    def test_existe_job_em_execucao(self):
        self.assertFalse(existe_job_em_execucao("health_scan"))

        JobExecution.objects.create(
            job_name="health_scan",
            status=JobExecution.STATUS_RUNNING,
            result={},
        )

        self.assertTrue(existe_job_em_execucao("health_scan"))

    def test_executar_job_com_lock_sucesso(self):
        def tarefa():
            return {"ok": True, "executado": True}

        registrar_job_agendado(
            ScheduledJob(
                name="health_scan",
                description="Health",
                handler=tarefa,
            )
        )

        job = executar_job_agendado_com_lock("health_scan")

        self.assertEqual(job.status, JobExecution.STATUS_SUCCESS)
        self.assertTrue(job.result.get("executado"))

    def test_executar_job_com_lock_bloqueia_concorrente(self):
        JobExecution.objects.create(
            job_name="km_reindex",
            status=JobExecution.STATUS_RUNNING,
            result={},
        )

        with self.assertRaises(JobAlreadyRunningError):
            executar_job_agendado_com_lock("km_reindex")

    def test_marcar_jobs_presos_como_falha(self):
        antigo = timezone.now() - timezone.timedelta(hours=3)

        job = JobExecution.objects.create(
            job_name="km_reindex",
            status=JobExecution.STATUS_RUNNING,
            started_at=antigo,
            result={},
        )

        total = marcar_jobs_presos_como_falha(minutos=60)

        job.refresh_from_db()

        self.assertEqual(total, 1)
        self.assertEqual(job.status, JobExecution.STATUS_FAILED)
        self.assertIn("timeout", job.error.lower())
