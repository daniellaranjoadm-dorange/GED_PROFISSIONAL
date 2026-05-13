from django.test import TestCase

from apps.automacoes.models import JobExecution, SchedulerState
from apps.automacoes.services.scheduler_state import (
    calcular_proxima_execucao,
    obter_ou_criar_scheduler_state,
    registrar_fim_job,
    registrar_inicio_job,
)


class SchedulerStateTests(TestCase):
    def test_obter_ou_criar_scheduler_state(self):
        state = obter_ou_criar_scheduler_state("health_scan")

        self.assertEqual(state.job_name, "health_scan")
        self.assertEqual(state.last_status, SchedulerState.STATUS_IDLE)

    def test_registrar_inicio_job(self):
        state = registrar_inicio_job("health_scan")

        self.assertEqual(state.last_status, SchedulerState.STATUS_RUNNING)
        self.assertIsNotNone(state.last_run_at)
        self.assertIsNotNone(state.heartbeat_at)

    def test_registrar_fim_job_success(self):
        job = JobExecution.objects.create(
            job_name="health_scan",
            status=JobExecution.STATUS_SUCCESS,
            result={"ok": True},
        )

        state = registrar_fim_job(job)

        self.assertEqual(state.last_status, SchedulerState.STATUS_SUCCESS)
        self.assertIsNotNone(state.last_success_at)
        self.assertIsNotNone(state.next_run_at)

    def test_registrar_fim_job_failed(self):
        job = JobExecution.objects.create(
            job_name="km_reindex",
            status=JobExecution.STATUS_FAILED,
            result={"ok": False},
            error="falha simulada",
        )

        state = registrar_fim_job(job)

        self.assertEqual(state.last_status, SchedulerState.STATUS_FAILED)
        self.assertIsNotNone(state.last_failure_at)
        self.assertIn("falha", state.runtime_notes)

    def test_calcular_proxima_execucao(self):
        proxima = calcular_proxima_execucao("health_scan")

        self.assertIsNotNone(proxima)
