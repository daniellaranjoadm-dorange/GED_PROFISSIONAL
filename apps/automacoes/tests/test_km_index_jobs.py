from django.test import TestCase

from apps.automacoes.models import JobExecution
from apps.automacoes.services.km_index_jobs import (
    executar_reindexacao_km_job,
    resultado_job_para_automacao,
)


class KMIndexJobsTests(TestCase):
    def test_executar_reindexacao_km_job_com_sucesso(self):
        def executor():
            return {
                "ok": True,
                "mensagem": "Índice KM atualizado.",
                "quantidade_processada": 10,
            }

        job = executar_reindexacao_km_job(
            payload={"origem_teste": "unit"},
            executor=executor,
        )

        self.assertEqual(job.job_name, "km_index_rebuild")
        self.assertEqual(job.status, JobExecution.STATUS_SUCCESS)
        self.assertEqual(job.payload["origem"], "km_index")
        self.assertEqual(job.payload["modo"], "sync")
        self.assertEqual(job.payload["origem_teste"], "unit")
        self.assertEqual(job.result["quantidade_processada"], 10)
        self.assertEqual(job.error, "")
        resultado = resultado_job_para_automacao(job)
        self.assertTrue(resultado["ok"])
        self.assertEqual(resultado["quantidade_processada"], 10)

    def test_executar_reindexacao_km_job_com_falha(self):
        def executor():
            raise RuntimeError("falha simulada")

        job = executar_reindexacao_km_job(executor=executor)

        self.assertEqual(job.job_name, "km_index_rebuild")
        self.assertEqual(job.status, JobExecution.STATUS_FAILED)
        self.assertIn("falha simulada", job.error)
        self.assertEqual(job.result.get("ok"), False)
        self.assertEqual(job.result.get("erro"), "falha simulada")
        resultado = resultado_job_para_automacao(job)
        self.assertFalse(resultado["ok"])
        self.assertIn("falha simulada", resultado["mensagem"])
