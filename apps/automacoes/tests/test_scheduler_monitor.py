from django.test import TestCase
from django.utils import timezone

from apps.automacoes.models import SchedulerState
from apps.automacoes.services.scheduler_monitor import obter_scheduler_monitoring


class SchedulerMonitorTests(TestCase):
    def test_obter_scheduler_monitoring(self):
        SchedulerState.objects.create(
            job_name="health_scan",
            last_status=SchedulerState.STATUS_SUCCESS,
            heartbeat_at=timezone.now(),
            next_run_at=timezone.now(),
        )

        dados = obter_scheduler_monitoring()

        self.assertIn("runtime_health", dados)
        self.assertIn("states", dados)
        self.assertEqual(dados["runtime_health"]["total"], 1)

    def test_detecta_job_vencido(self):
        SchedulerState.objects.create(
            job_name="km_reindex",
            last_status=SchedulerState.STATUS_IDLE,
            heartbeat_at=timezone.now(),
            next_run_at=timezone.now() - timezone.timedelta(minutes=5),
        )

        dados = obter_scheduler_monitoring()

        self.assertEqual(dados["vencidos"].count(), 1)
