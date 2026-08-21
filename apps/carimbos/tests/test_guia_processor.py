import tempfile
from pathlib import Path

from django.contrib.auth import get_user_model
from django.test import TestCase
from reportlab.pdfgen import canvas

from apps.carimbos.models import DistribuicaoCopia
from apps.carimbos.services.guia_processor import carregar_previa, listar_guias, processar_guia
from apps.carimbos.services.revision_control import analisar_revisoes, comparar_revisoes


def criar_pdf_documento(caminho: Path):
    pdf = canvas.Canvas(str(caminho), pagesize=(400, 600))
    pdf.drawString(35, 550, "DOCUMENTO CONTROLADO")
    pdf.save()


def criar_guia(raiz: Path, numero: str, revisao: str):
    pasta = raiz / numero
    pasta.mkdir()
    criar_pdf_documento(pasta / "83100-ECXP00046_00-5G-DE-0005.01.pdf")

    pdf = canvas.Canvas(str(raiz / f"{numero}.pdf"), pagesize=(900, 700))
    linhas = [
        (620, numero.replace("-", "/", 1).replace("_", "/")),
        (600, "Data: 30/07/2026 10:02"),
        (580, "A/C: Carlos Miranda - Fone: - (carlos@empresa.com.br)"),
        (560, "Remetente: DANIEL ALVES LARANJO - (daniel@empresa.com.br)"),
        (520, f"83100-ECXP00046/00-5G-DE-0005.01          01       {revisao}    PLATE NESTING"),
        (470, "ALESSANDRO VIEIRA DE ABREU          alessandro@empresa.com.br"),
        (450, "TELMO RODRIGUES                     telmo@empresa.com.br"),
        (430, "Engenharia                           engenharia@ecovix.com"),
        (410, "Planejamneto                         planejamento@ecovix.com"),
        (390, "Controle de Qualidade                cq@ecovix.com"),
    ]
    for y, texto in linhas:
        pdf.drawString(40, y, texto)
    pdf.save()


class GuiaProcessorTests(TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.raiz = Path(self.temp_dir.name)
        self.override = self.settings(GUIAS_EMISSAO_ROOT=self.raiz)
        self.override.enable()
        self.addCleanup(self.override.disable)
        self.addCleanup(self.temp_dir.cleanup)
        self.usuario = get_user_model().objects.create_user(
            username="operador.gi",
            password="senha-segura-123",
        )

    def test_le_guia_remetente_documento_revisao_e_destinatarios(self):
        numero = "ECXP00046-00-10-GI-0006_26"
        criar_guia(self.raiz, numero, "0")
        dados = carregar_previa(numero)
        self.assertEqual(dados.remetente, "DANIEL ALVES LARANJO")
        self.assertEqual(dados.documentos[0].revisao, "0")
        self.assertEqual(
            {p.nome for p in dados.destinatarios},
            {
                "Carlos Miranda",
                "ALESSANDRO VIEIRA DE ABREU",
                "TELMO RODRIGUES",
                "Engenharia",
                "Planejamento",
                "Controle de Qualidade",
                "Transpetro",
                "SMS",
                "SGI",
                "Desmantelamento",
                "Produção",
            },
        )
        encontrados = {p.nome: p.na_guia for p in dados.destinatarios}
        self.assertTrue(encontrados["Planejamento"])
        self.assertFalse(encontrados["Transpetro"])
        self.assertFalse(encontrados["SMS"])

    def test_le_e_lista_ge_com_sequencial_de_cinco_digitos(self):
        numero = "ECXP00046-00-10-GE-00199_26"
        criar_guia(self.raiz, numero, "0")

        dados = carregar_previa(numero)

        self.assertEqual(dados.numero, numero)
        self.assertIn(numero, listar_guias())
        self.assertEqual(dados.documentos[0].revisao, "0")

    def test_le_e_lista_ge_quando_pdf_da_guia_esta_na_subpasta(self):
        numero = "ECXP00046-00-10-GE-00199_26"
        criar_guia(self.raiz, numero, "0")
        guia_na_raiz = self.raiz / f"{numero}.pdf"
        guia_na_pasta = self.raiz / numero / f"{numero}.pdf"
        guia_na_raiz.replace(guia_na_pasta)

        dados = carregar_previa(numero)

        self.assertTrue(dados.caminho.samefile(guia_na_pasta))
        self.assertIn(numero, listar_guias())

    def test_nova_revisao_abre_recolhimento_da_anterior(self):
        gi_rev_0 = "ECXP00046-00-10-GI-0006_26"
        gi_rev_1 = "ECXP00046-00-10-GI-0007_26"
        criar_guia(self.raiz, gi_rev_0, "0")
        criar_guia(self.raiz, gi_rev_1, "1")
        pessoas = [
            "Carlos Miranda",
            "ALESSANDRO VIEIRA DE ABREU",
            "TELMO RODRIGUES",
        ]

        primeira = processar_guia(
            gi_rev_0,
            destinatarios_selecionados=pessoas,
            usuario=self.usuario,
        )
        segunda = processar_guia(
            gi_rev_1,
            destinatarios_selecionados=pessoas,
            usuario=self.usuario,
        )

        self.assertEqual(primeira.copias_geradas, 3)
        self.assertEqual(segunda.copias_geradas, 3)
        self.assertEqual(segunda.recolhimentos_abertos, 3)
        self.assertEqual(
            DistribuicaoCopia.objects.filter(
                revisao="0",
                status=DistribuicaoCopia.STATUS_RECOLHIMENTO_PENDENTE,
            ).count(),
            3,
        )
        self.assertEqual(
            DistribuicaoCopia.objects.filter(
                revisao="1",
                status=DistribuicaoCopia.STATUS_EMITIDA,
            ).count(),
            3,
        )
        repetida = processar_guia(
            gi_rev_1,
            destinatarios_selecionados=pessoas,
            usuario=self.usuario,
        )
        self.assertEqual(repetida.copias_geradas, 0)
        self.assertEqual(repetida.copias_atualizadas, 3)
        self.assertEqual(DistribuicaoCopia.objects.count(), 6)

    def test_compara_sequencias_numerica_e_alfabetica_sem_misturar_familias(self):
        self.assertEqual(comparar_revisoes("2", "1"), 1)
        self.assertEqual(comparar_revisoes("0", "1"), -1)
        self.assertEqual(comparar_revisoes("C", "B"), 1)
        self.assertEqual(comparar_revisoes("A", "B"), -1)
        self.assertEqual(comparar_revisoes("B", "B"), 0)
        self.assertIsNone(comparar_revisoes("A", "2"))

    def test_previa_informa_destinatario_revisao_e_guia_anterior(self):
        gi_anterior = "ECXP00046-00-10-GI-0006_26"
        gi_nova = "ECXP00046-00-10-GI-0007_26"
        criar_guia(self.raiz, gi_anterior, "A")
        criar_guia(self.raiz, gi_nova, "B")
        processar_guia(
            gi_anterior,
            destinatarios_selecionados=["Carlos Miranda"],
            usuario=self.usuario,
        )

        analise = analisar_revisoes(carregar_previa(gi_nova))

        self.assertEqual(len(analise.impactos), 1)
        impacto = analise.impactos[0]
        self.assertEqual(impacto.destinatario, "Carlos Miranda")
        self.assertEqual(impacto.revisao_anterior, "A")
        self.assertEqual(impacto.revisao_nova, "B")
        self.assertEqual(impacto.guia_anterior, gi_anterior)

    def test_revisao_inferior_nao_abre_recolhimento(self):
        gi_rev_2 = "ECXP00046-00-10-GI-0006_26"
        gi_rev_1 = "ECXP00046-00-10-GI-0007_26"
        criar_guia(self.raiz, gi_rev_2, "2")
        criar_guia(self.raiz, gi_rev_1, "1")
        processar_guia(
            gi_rev_2,
            destinatarios_selecionados=["Carlos Miranda"],
            usuario=self.usuario,
        )

        resultado = processar_guia(
            gi_rev_1,
            destinatarios_selecionados=["Carlos Miranda"],
            usuario=self.usuario,
        )

        self.assertEqual(resultado.recolhimentos_abertos, 0)
        self.assertEqual(
            DistribuicaoCopia.objects.get(revisao="2").status,
            DistribuicaoCopia.STATUS_EMITIDA,
        )

    def test_nome_editado_e_usado_somente_no_carimbo(self):
        numero = "ECXP00046-00-10-GI-0006_26"
        criar_guia(self.raiz, numero, "0")

        resultado = processar_guia(
            numero,
            destinatarios_selecionados=["Carlos Miranda"],
            nomes_carimbo={"Carlos Miranda": "Nome Manual no Carimbo"},
            meios_distribuicao={"Carlos Miranda": "FISICO"},
            quantidades={"Carlos Miranda": 2},
            usuario=self.usuario,
        )

        distribuicao = DistribuicaoCopia.objects.get(guia=resultado.guia)
        self.assertEqual(distribuicao.destinatario, "Carlos Miranda")
        self.assertEqual(distribuicao.recebedor_carimbo, "Nome Manual no Carimbo")
        self.assertEqual(distribuicao.meio_distribuicao, DistribuicaoCopia.MEIO_FISICO)
        self.assertEqual(distribuicao.quantidade, 2)
        self.assertEqual(
            Path(distribuicao.caminho_copia).name,
            (
                "83100-ECXP00046_00-5G-DE-0005.01_"
                "ECXP00046-00-10-GI-0006_26_Nome_Manual_no_Carimbo.pdf"
            ),
        )
        texto = "".join(
            pagina.extract_text() or ""
            for pagina in __import__("pypdf").PdfReader(distribuicao.caminho_copia).pages
        )
        self.assertIn("Nome Manual no Carimbo", texto)

        repetido = processar_guia(
            numero,
            destinatarios_selecionados=["Carlos Miranda"],
            nomes_carimbo={"Carlos Miranda": "Ismael Cardoso"},
            usuario=self.usuario,
        )
        distribuicao.refresh_from_db()
        texto_atualizado = "".join(
            pagina.extract_text() or ""
            for pagina in __import__("pypdf").PdfReader(distribuicao.caminho_copia).pages
        )
        self.assertEqual(repetido.copias_atualizadas, 1)
        self.assertIn("Ismael Cardoso", texto_atualizado)
        self.assertNotIn("Nome Manual no Carimbo", texto_atualizado)
