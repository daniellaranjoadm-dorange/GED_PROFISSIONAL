from django.test import TestCase
from django.utils import timezone

from apps.automacoes.models import JobExecution, SchedulerState
from apps.automacoes.services.scheduler import limpar_registry_jobs_agendados
from apps.automacoes.services.scheduler_engine import (
    inicializar_scheduler_states,
    listar_jobs_vencidos,
    scheduler_tick,
)


class SchedulerEngineTests(TestCase):
    def tearDown(self):
        limpar_registry_jobs_agendados()

    def test_inicializar_scheduler_states(self):
        states = inicializar_scheduler_states()

        nomes = {state.job_name for state in states}

        self.assertIn("health_scan", nomes)
        self.assertIn("km_reindex", nomes)

    def test_listar_jobs_vencidos(self):
        SchedulerState.objects.create(
            job_name="vencido",
            enabled=True,
            next_run_at=timezone.now() - timezone.timedelta(minutes=1),
        )
        SchedulerState.objects.create(
            job_name="futuro",
            enabled=True,
            next_run_at=timezone.now() + timezone.timedelta(minutes=10),
        )

        vencidos = list(listar_jobs_vencidos())

        self.assertEqual(len(vencidos), 1)
        self.assertEqual(vencidos[0].job_name, "vencido")

    def test_scheduler_tick_executa_health_scan_vencido(self):
        inicializar_scheduler_states()

        state = SchedulerState.objects.get(job_name="health_scan")
        state.next_run_at = timezone.now() - timezone.timedelta(minutes=1)
        state.save(update_fields=["next_run_at", "updated_at"])

        resultado = scheduler_tick(limit=5)

        self.assertTrue(resultado["ok"])
        self.assertGreaterEqual(resultado["total_executados"], 1)
        self.assertTrue(
            JobExecution.objects.filter(
                job_name="health_scan",
                status=JobExecution.STATUS_SUCCESS,
            ).exists()
        )

    def test_scheduler_tick_nao_executa_job_futuro(self):
        inicializar_scheduler_states()

        SchedulerState.objects.filter(job_name="health_scan").update(
            next_run_at=timezone.now() + timezone.timedelta(hours=1)
        )
        SchedulerState.objects.filter(job_name="km_reindex").update(
            next_run_at=timezone.now() + timezone.timedelta(hours=1)
        )

        resultado = scheduler_tick(limit=5)

        self.assertEqual(resultado["total_executados"], 0)
