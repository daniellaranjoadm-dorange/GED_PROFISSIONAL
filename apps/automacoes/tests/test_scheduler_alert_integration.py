from django.test import TestCase
from django.utils import timezone

from apps.automacoes.models import RuntimeAlert, SchedulerState
from apps.automacoes.services.scheduler import limpar_registry_jobs_agendados
from apps.automacoes.services.scheduler_engine import scheduler_tick


class SchedulerAlertIntegrationTests(TestCase):
    def tearDown(self):
        limpar_registry_jobs_agendados()

    def test_scheduler_tick_detecta_alerta_de_job_falhando(self):
        SchedulerState.objects.create(
            job_name="km_reindex",
            enabled=True,
            last_status=SchedulerState.STATUS_FAILED,
            heartbeat_at=timezone.now(),
            next_run_at=timezone.now() + timezone.timedelta(hours=1),
            runtime_notes="falha anterior",
        )

        resultado = scheduler_tick(limit=5)

        self.assertEqual(resultado["total_alertas"], 1)
        self.assertTrue(
            RuntimeAlert.objects.filter(
                codigo="JOB_FAILED",
                job_name="km_reindex",
                resolvido=False,
            ).exists()
        )

    def test_scheduler_tick_pode_ignorar_detecao_de_alertas(self):
        SchedulerState.objects.create(
            job_name="km_reindex",
            enabled=True,
            last_status=SchedulerState.STATUS_FAILED,
            heartbeat_at=timezone.now(),
            next_run_at=timezone.now() + timezone.timedelta(hours=1),
        )

        resultado = scheduler_tick(limit=5, detectar_alertas=False)

        self.assertEqual(resultado["total_alertas"], 0)
        self.assertEqual(RuntimeAlert.objects.count(), 0)
