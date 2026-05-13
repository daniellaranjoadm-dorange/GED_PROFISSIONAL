from django.contrib.auth import get_user_model
from django.test import TestCase

from apps.automacoes.models import SearchAudit
from apps.automacoes.services.search_audit import registrar_busca
from apps.automacoes.services.search_engine import buscar_global_enterprise


class SearchAuditTests(TestCase):
    def test_registrar_busca_grava_totais(self):
        audit = registrar_busca(
            termo="MA-001",
            tipo="todos",
            origem=SearchAudit.ORIGEM_WEB,
            totais_reais={
                "km": 2,
                "transmittals": 1,
                "ld": 3,
                "pcfs": 4,
            },
            duracao_ms=12,
        )

        self.assertIsNotNone(audit)
        self.assertEqual(SearchAudit.objects.count(), 1)
        self.assertEqual(audit.total_geral, 10)
        self.assertEqual(audit.total_km, 2)
        self.assertEqual(audit.total_pcfs, 4)

    def test_registrar_busca_ignora_termo_vazio(self):
        audit = registrar_busca(termo="", totais_reais={"km": 1})

        self.assertIsNone(audit)
        self.assertEqual(SearchAudit.objects.count(), 0)

    def test_busca_global_enterprise_audita_quando_solicitado(self):
        User = get_user_model()
        usuario = User.objects.create_user(username="auditor", password="x")

        contexto = buscar_global_enterprise(
            "ZZ-SEM-RESULTADO",
            usuario=usuario,
            origem=SearchAudit.ORIGEM_WEB,
            auditar=True,
        )

        self.assertEqual(contexto["totais"]["geral"], 0)
        self.assertEqual(SearchAudit.objects.count(), 1)

        audit = SearchAudit.objects.first()
        self.assertEqual(audit.usuario, usuario)
        self.assertEqual(audit.termo, "ZZ-SEM-RESULTADO")
        self.assertEqual(audit.total_geral, 0)
