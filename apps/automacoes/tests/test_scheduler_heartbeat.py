from django.test import TestCase
from django.utils import timezone

from apps.automacoes.models import SchedulerState
from apps.automacoes.services.scheduler_heartbeat import (
    listar_states_obsoletos,
    obter_runtime_health,
    registrar_heartbeat,
    scheduler_state_esta_obsoleto,
)


class SchedulerHeartbeatTests(TestCase):
    def test_registrar_heartbeat(self):
        state = registrar_heartbeat("health_scan", note="ok")

        self.assertIsNotNone(state.heartbeat_at)
        self.assertEqual(state.runtime_notes, "ok")

    def test_scheduler_state_esta_obsoleto(self):
        state = SchedulerState.objects.create(
            job_name="km_reindex",
            heartbeat_at=timezone.now() - timezone.timedelta(hours=2),
        )

        self.assertTrue(scheduler_state_esta_obsoleto(state, minutos=30))

    def test_listar_states_obsoletos(self):
        SchedulerState.objects.create(
            job_name="antigo",
            heartbeat_at=timezone.now() - timezone.timedelta(hours=2),
        )
        SchedulerState.objects.create(
            job_name="novo",
            heartbeat_at=timezone.now(),
        )

        qs = listar_states_obsoletos(minutos=30)

        self.assertEqual(qs.count(), 1)
        self.assertEqual(qs.first().job_name, "antigo")

    def test_obter_runtime_health(self):
        SchedulerState.objects.create(
            job_name="health_scan",
            last_status=SchedulerState.STATUS_SUCCESS,
            heartbeat_at=timezone.now(),
        )

        health = obter_runtime_health()

        self.assertEqual(health["total"], 1)
        self.assertTrue(health["healthy"])
