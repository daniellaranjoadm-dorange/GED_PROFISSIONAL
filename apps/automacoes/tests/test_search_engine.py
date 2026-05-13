from django.test import TestCase

from apps.automacoes.models import DocumentoLD, KMFileIndex
from apps.automacoes.services.search_engine import buscar_global, normalizar_termo_busca


class SearchEngineTests(TestCase):
    def test_normalizar_termo_busca_remove_espacos_externos(self):
        self.assertEqual(normalizar_termo_busca("  24-7141  "), "24-7141")

    def test_busca_vazia_retorna_resultado_estavel(self):
        resultado = buscar_global("")

        self.assertEqual(resultado["termo"], "")
        self.assertEqual(resultado["total"], 0)
        self.assertEqual(resultado["ld"], [])
        self.assertEqual(resultado["km"], [])
        self.assertEqual(resultado["resultados"], [])

    def test_busca_ld_por_documento(self):
        DocumentoLD.objects.create(
            documento="24-7141-00-MA-001",
            titulo="Memorial de cálculo",
        )

        resultado = buscar_global("MA-001")

        self.assertEqual(len(resultado["ld"]), 1)
        self.assertEqual(resultado["ld"][0]["origem"], "LD")
        self.assertEqual(resultado["ld"][0]["identificador"], "24-7141-00-MA-001")

    def test_busca_km_por_documento_indexado(self):
        KMFileIndex.objects.create(
            caminho_completo=r"\\servidor\km\24-7141-00-DE-001.docx",
            nome_arquivo="24-7141-00-DE-001.docx",
            pasta=r"\\servidor\km",
            extensao=".docx",
            nome_normalizado="24714100DE001DOCX",
            stem_normalizado="24714100DE001",
            documento_extraido="24-7141-00-DE-001",
            ativo=True,
            eh_transmittal_letter=False,
        )

        resultado = buscar_global("DE-001")

        self.assertEqual(len(resultado["km"]), 1)
        self.assertEqual(resultado["km"][0]["origem"], "KM")
        self.assertEqual(resultado["km"][0]["identificador"], "24-7141-00-DE-001")
