from django.test import TestCase

from apps.automacoes.models import JobExecution
from apps.automacoes.services.job_manager import (
    criar_job,
    executar_job_sincrono,
    job_executou_com_sucesso,
)


class JobManagerTests(TestCase):
    def test_criar_job_pendente(self):
        job = criar_job("km_index", payload={"origem": "teste"})

        self.assertEqual(job.job_name, "km_index")
        self.assertEqual(job.status, JobExecution.STATUS_PENDING)
        self.assertEqual(job.payload, {"origem": "teste"})

    def test_executar_job_sincrono_com_sucesso(self):
        def tarefa():
            return {"ok": True, "processados": 10}

        job = executar_job_sincrono("tarefa_teste", tarefa)

        self.assertEqual(job.status, JobExecution.STATUS_SUCCESS)
        self.assertTrue(job_executou_com_sucesso(job))
        self.assertEqual(job.result["processados"], 10)
        self.assertGreaterEqual(job.duration_ms, 0)

    def test_executar_job_sincrono_com_falha(self):
        def tarefa():
            raise ValueError("falha controlada")

        job = executar_job_sincrono("tarefa_falha", tarefa)

        self.assertEqual(job.status, JobExecution.STATUS_FAILED)
        self.assertFalse(job_executou_com_sucesso(job))
        self.assertIn("falha controlada", job.error)
        self.assertFalse(job.result["ok"])
