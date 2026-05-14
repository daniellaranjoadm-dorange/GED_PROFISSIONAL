from django.test import TestCase
from django.utils import timezone

from apps.automacoes.models import JobExecution, RuntimeAlert, SchedulerState
from apps.automacoes.services.runtime_healing import (
    executar_self_healing_runtime,
    recuperar_jobs_running_presos,
    recuperar_scheduler_states_stale,
)


class RuntimeHealingTests(TestCase):
    def test_recuperar_jobs_running_presos(self):
        antigo = timezone.now() - timezone.timedelta(hours=5)

        job = JobExecution.objects.create(
            job_name="km_reindex",
            status=JobExecution.STATUS_RUNNING,
            started_at=antigo,
            result={},
        )

        resultado = recuperar_jobs_running_presos(minutos=60)

        job.refresh_from_db()

        self.assertTrue(resultado["ok"])
        self.assertEqual(resultado["total"], 1)
        self.assertEqual(job.status, JobExecution.STATUS_FAILED)
        self.assertTrue(
            RuntimeAlert.objects.filter(
                codigo="JOB_TIMEOUT_RECOVERED",
                job_name="km_reindex",
            ).exists()
        )

    def test_nao_recupera_job_running_recente(self):
        recente = timezone.now() - timezone.timedelta(minutes=5)

        job = JobExecution.objects.create(
            job_name="health_scan",
            status=JobExecution.STATUS_RUNNING,
            started_at=recente,
            result={},
        )

        resultado = recuperar_jobs_running_presos(minutos=60)

        job.refresh_from_db()

        self.assertEqual(resultado["total"], 0)
        self.assertEqual(job.status, JobExecution.STATUS_RUNNING)

    def test_recuperar_scheduler_states_stale(self):
        state = SchedulerState.objects.create(
            job_name="health_scan",
            heartbeat_at=timezone.now() - timezone.timedelta(hours=2),
            last_status=SchedulerState.STATUS_RUNNING,
        )

        resultado = recuperar_scheduler_states_stale(minutos=30)

        state.refresh_from_db()

        self.assertTrue(resultado["ok"])
        self.assertEqual(resultado["total"], 1)
        self.assertEqual(state.last_status, SchedulerState.STATUS_FAILED)
        self.assertIsNotNone(state.next_run_at)
        self.assertTrue(
            RuntimeAlert.objects.filter(
                codigo="SCHEDULER_STATE_RECOVERED",
                job_name="health_scan",
            ).exists()
        )

    def test_executar_self_healing_runtime(self):
        JobExecution.objects.create(
            job_name="km_reindex",
            status=JobExecution.STATUS_RUNNING,
            started_at=timezone.now() - timezone.timedelta(hours=5),
            result={},
        )
        SchedulerState.objects.create(
            job_name="health_scan",
            heartbeat_at=timezone.now() - timezone.timedelta(hours=2),
            last_status=SchedulerState.STATUS_RUNNING,
        )

        resultado = executar_self_healing_runtime()

        self.assertTrue(resultado["ok"])
        self.assertEqual(resultado["jobs_recuperados"], 1)
        self.assertEqual(resultado["states_recuperados"], 1)
