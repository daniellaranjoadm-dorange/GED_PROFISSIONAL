from django.test import TestCase

from apps.automacoes.models import JobExecution
from apps.automacoes.services.scheduler import (
    ScheduledJob,
    executar_job_agendado,
    limpar_registry_jobs_agendados,
    listar_jobs_agendados,
    obter_job_agendado,
    registrar_job_agendado,
)


class SchedulerFoundationTests(TestCase):
    def tearDown(self):
        limpar_registry_jobs_agendados()

    def test_registrar_e_listar_job_agendado(self):
        def tarefa():
            return {"ok": True}

        registrar_job_agendado(
            ScheduledJob(
                name="teste",
                description="Job de teste",
                handler=tarefa,
            )
        )

        jobs = list(listar_jobs_agendados())

        self.assertEqual(len(jobs), 1)
        self.assertEqual(jobs[0].name, "teste")
        self.assertIsNotNone(obter_job_agendado("teste"))

    def test_executar_job_agendado_com_sucesso(self):
        def tarefa():
            return {"ok": True, "valor": 10}

        registrar_job_agendado(
            ScheduledJob(
                name="job_ok",
                description="Job OK",
                handler=tarefa,
            )
        )

        job = executar_job_agendado("job_ok")

        self.assertEqual(job.status, JobExecution.STATUS_SUCCESS)
        self.assertEqual(job.result.get("valor"), 10)

    def test_executar_job_agendado_inexistente_gera_erro(self):
        with self.assertRaises(ValueError):
            executar_job_agendado("nao_existe")

    def test_job_desabilitado_nao_executa(self):
        def tarefa():
            return {"ok": True}

        registrar_job_agendado(
            ScheduledJob(
                name="job_disabled",
                description="Job desabilitado",
                handler=tarefa,
                enabled=False,
            )
        )

        self.assertEqual(list(listar_jobs_agendados()), [])

        with self.assertRaises(ValueError):
            executar_job_agendado("job_disabled")
