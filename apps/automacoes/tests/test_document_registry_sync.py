from django.test import TestCase

from apps.automacoes.models import DocumentoLD
from apps.automacoes.services.document_registry_sync import (
    cadastrar_documentos_ausentes_da_ld,
    normalizar_identificador,
    normalizar_revisao,
    sincronizar_documentos_ld_com_ged,
)
from apps.documentos.models import Documento, LogAuditoria


class DocumentRegistrySyncTests(TestCase):
    def test_cadastra_ausente_uma_vez_e_vincula_ld(self):
        registro = DocumentoLD.objects.create(
            origem_aba="LD Marenova Executivo",
            documento="DOC-NOVO-001",
            revisao="A",
            titulo="Documento novo",
            disciplina="Estrutura",
            status_documento="Recebido",
            status_grd="Emitido",
        )

        resultado = cadastrar_documentos_ausentes_da_ld()
        segunda_execucao = cadastrar_documentos_ausentes_da_ld()

        registro.refresh_from_db()
        self.assertEqual(resultado["criados"], 1)
        self.assertEqual(segunda_execucao["criados"], 0)
        self.assertEqual(Documento.objects.filter(codigo="DOC-NOVO-001").count(), 1)
        self.assertEqual(registro.documento_ged.titulo, "Documento novo")
        self.assertTrue(
            LogAuditoria.objects.filter(
                documento=registro.documento_ged,
                acao="Cadastro automático via LD",
            ).exists()
        )

    def test_normaliza_codigo_e_revisao(self):
        self.assertEqual(normalizar_identificador("I-LD-4880.00"), "ILD488000")
        self.assertEqual(normalizar_revisao("Rev. 00"), "0")

    def test_vincula_apenas_correspondencia_unica_de_codigo_e_revisao(self):
        documento = Documento.objects.create(
            codigo="I-LD-4880.00-9311-000-CZ1-001",
            revisao="0",
            titulo="Lista de documentos",
        )
        registro = DocumentoLD.objects.create(
            origem_aba="LD PROJETO BASICO",
            documento="I LD 4880.00 9311 000 CZ1 001",
            revisao="Rev. 00",
        )

        resultado = sincronizar_documentos_ld_com_ged()

        registro.refresh_from_db()
        self.assertEqual(registro.documento_ged, documento)
        self.assertEqual(resultado["vinculados"], 1)

    def test_nao_adivinha_quando_ha_duplicidade_no_cadastro_central(self):
        for titulo in ("A", "B"):
            Documento.objects.create(codigo="DOC-001", revisao="A", titulo=titulo)
        registro = DocumentoLD.objects.create(
            origem_aba="LD",
            documento="DOC-001",
            revisao="A",
        )

        resultado = sincronizar_documentos_ld_com_ged()

        registro.refresh_from_db()
        self.assertIsNone(registro.documento_ged)
        self.assertEqual(resultado["ambiguos"], 1)
