from pathlib import Path
from tempfile import TemporaryDirectory

from django.test import SimpleTestCase, override_settings

from apps.automacoes.services.ld_path_resolver import (
    resolver_caminho_ld,
    selecionar_arquivo_documental,
)


class LDPathResolverTests(SimpleTestCase):
    def test_pasta_prioriza_pdf_depois_word_excel_e_nativo(self):
        with TemporaryDirectory() as tmp:
            pasta = Path(tmp)
            nativo = pasta / "desenho.dwg"
            planilha = pasta / "dados.xlsx"
            word = pasta / "memorial.docx"
            pdf = pasta / "documento.pdf"
            for arquivo in (nativo, planilha, word, pdf):
                arquivo.write_bytes(b"teste")

            self.assertEqual(selecionar_arquivo_documental(pasta), pdf)
            pdf.unlink()
            self.assertEqual(selecionar_arquivo_documental(pasta), word)
            word.unlink()
            self.assertEqual(selecionar_arquivo_documental(pasta), planilha)
            planilha.unlink()
            self.assertEqual(selecionar_arquivo_documental(pasta), nativo)

    def test_resolve_caminho_absoluto_existente(self):
        with TemporaryDirectory() as tmp:
            arquivo = Path(tmp) / "documento.xlsx"
            arquivo.write_text("teste", encoding="utf-8")

            resolvido, caminhos_testados = resolver_caminho_ld(str(arquivo))

            self.assertEqual(Path(resolvido), arquivo)
            self.assertIsInstance(caminhos_testados, list)

    def test_resolve_caminho_relativo_com_base_configurada(self):
        with TemporaryDirectory() as tmp:
            raiz = Path(tmp)
            arquivo = raiz / "9 - PCFs Transpetro" / "PCF-TESTE.xlsx"
            arquivo.parent.mkdir(parents=True, exist_ok=True)
            arquivo.write_text("teste", encoding="utf-8")

            with override_settings(LD_BASE_PATH=str(raiz)):
                resolvido, caminhos_testados = resolver_caminho_ld("../9 - PCFs Transpetro/PCF-TESTE.xlsx")

            self.assertEqual(Path(resolvido), arquivo)
            self.assertIsInstance(caminhos_testados, list)

    def test_retorna_none_quando_caminho_vazio(self):
        resolvido, caminhos_testados = resolver_caminho_ld("")
        self.assertIsNone(resolvido)
        self.assertEqual(caminhos_testados, [])

        resolvido, caminhos_testados = resolver_caminho_ld(None)
        self.assertIsNone(resolvido)
        self.assertEqual(caminhos_testados, [])
