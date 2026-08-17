from pathlib import Path
from tempfile import TemporaryDirectory

from django.test import SimpleTestCase, override_settings
from openpyxl import Workbook

from apps.carimbos.services.guia_parser import DocumentoGuia
from apps.carimbos.services.shopdrawing_distribution import montar_matriz_previa


REGRAS = """Assembly Plan
Controle de Qualidade - 1 cópia física (Telmo)
Produção - Esmael e Renasci 1 cópia física
Planejamento - Angelo e Lessander apenas cópia digital
Fiscalização Transpetro - Ainda não tem pessoa definida

Panel Sketch
Produção - Ainda não tem pessoa definida
Controle de Qualidade - 1 cópia física (Telmo)
Planejamento - Angelo e Lessander apenas cópia digital

Bill of Material Plates e Profiles
Produção - 1 cópia física (Regis)
Controle de Qualidade - 1 cópia física (Telmo)
Planejamento - Angelo e Lessander apenas cópia digital
Logística - 1 cópia física (Alisson Clair)
"""


class ShopdrawingDistributionTests(SimpleTestCase):
    def setUp(self):
        self.tempdir = TemporaryDirectory(dir=Path.cwd() / ".test_tmp")
        self.root = Path(self.tempdir.name)
        self.rules_path = self.root / "distribuicao.txt"
        self.ld_path = self.root / "shopdrawings.xlsx"
        self.rules_path.write_text(REGRAS, encoding="utf-8")

        workbook = Workbook()
        sheet = workbook.active
        sheet.title = "SD-INDICE"
        sheet.append([f"Coluna {indice}" for indice in range(1, 18)])
        sheet.append([
            "DOC-ASSEMBLY", "", "", "ASSEMBLY PLAN BLOCK 01", "", "", "", "B",
            "", "", "", "", "", "", "", "https://dox/assembly", "",
        ])
        sheet.append([
            "DOC-PANEL", "", "", "PANEL SKETCH 02", "", "", "", "0",
            "", "", "", "", "", "", "", "https://dox/panel", "",
        ])
        sheet.append([
            "DOC-BOM", "", "", "BILL OF MATERIALS PLATES", "", "", "", "1",
            "", "", "", "", "", "", "", "https://dox/bom", "",
        ])
        workbook.save(self.ld_path)

    def tearDown(self):
        self.tempdir.cleanup()

    def _matriz(self, *documentos):
        with override_settings(
            SHOPDRAWING_DISTRIBUTION_FILE=self.rules_path,
            SHOPDRAWING_LD_FILE=self.ld_path,
        ):
            return montar_matriz_previa(tuple(documentos))

    def test_classifica_assembly_e_preserva_responsabilidade_pendente(self):
        item = self._matriz(DocumentoGuia("DOC-ASSEMBLY", "01", "B"))[0]
        self.assertEqual(item.categoria, "Assembly Plan")
        self.assertEqual(item.link_dox, "https://dox/assembly")
        self.assertEqual(
            {destino.pessoa for destino in item.destinos if destino.pessoa},
            {"Telmo", "Esmael", "Renasci", "Angelo", "Lessander"},
        )
        pendencia = next(destino for destino in item.destinos if destino.pendente)
        self.assertEqual(pendencia.setor, "Fiscalização Transpetro")
        self.assertEqual(pendencia.pessoa, "")

    def test_classifica_panel_e_bom_com_meios_corretos(self):
        panel, bom = self._matriz(
            DocumentoGuia("DOC-PANEL", "01", "0"),
            DocumentoGuia("DOC-BOM", "01", "1"),
        )
        self.assertEqual(panel.categoria, "Panel Sketch")
        self.assertTrue(any(item.setor == "Produção" and item.pendente for item in panel.destinos))
        planejamento = [item for item in panel.destinos if item.setor == "Planejamento"]
        self.assertTrue(planejamento)
        self.assertTrue(all(item.meio == "DIGITAL" for item in planejamento))
        self.assertEqual(bom.categoria, "Bill of Material")
        self.assertTrue(any(item.pessoa == "Alisson Clair" for item in bom.destinos))

    def test_documento_fora_da_ld_fica_explicito_sem_supor_regra(self):
        item = self._matriz(DocumentoGuia("DOC-INEXISTENTE", "01", "0"))[0]
        self.assertFalse(item.encontrado_ld)
        self.assertFalse(item.regra_encontrada)
        self.assertEqual(item.destinos, ())
