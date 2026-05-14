from django.test import TestCase
from django.utils import timezone

from apps.automacoes.models import RuntimeAlert, SchedulerState
from apps.automacoes.services.runtime_alerts import (
    criar_alerta_runtime,
    detectar_jobs_falhando,
    detectar_scheduler_stale,
    executar_varredura_alertas_runtime,
)


class RuntimeAlertsTests(TestCase):
    def test_criar_alerta_runtime(self):
        alerta = criar_alerta_runtime(
            codigo="TEST",
            titulo="Teste",
            mensagem="Mensagem",
        )

        self.assertEqual(alerta.codigo, "TEST")

    def test_criar_alerta_runtime_deduplica_alerta_aberto(self):
        criar_alerta_runtime(
            codigo="TEST",
            titulo="Teste",
            mensagem="Mensagem",
            job_name="health_scan",
        )
        segundo = criar_alerta_runtime(
            codigo="TEST",
            titulo="Teste",
            mensagem="Mensagem",
            job_name="health_scan",
        )

        self.assertIsNone(segundo)
        self.assertEqual(RuntimeAlert.objects.count(), 1)

    def test_detectar_scheduler_stale(self):
        SchedulerState.objects.create(
            job_name="health_scan",
            heartbeat_at=timezone.now() - timezone.timedelta(hours=2),
        )

        alertas = detectar_scheduler_stale(minutos=30)

        self.assertEqual(len(alertas), 1)

    def test_detectar_jobs_falhando(self):
        SchedulerState.objects.create(
            job_name="km_reindex",
            last_status=SchedulerState.STATUS_FAILED,
        )

        alertas = detectar_jobs_falhando()

        self.assertEqual(len(alertas), 1)
        self.assertEqual(alertas[0].codigo, "JOB_FAILED")

    def test_executar_varredura_alertas_runtime(self):
        SchedulerState.objects.create(
            job_name="km_reindex",
            last_status=SchedulerState.STATUS_FAILED,
        )

        resultado = executar_varredura_alertas_runtime()

        self.assertTrue(resultado["ok"])
        self.assertEqual(resultado["alertas_criados"], 1)
        self.assertIn("JOB_FAILED", resultado["codigos"])
