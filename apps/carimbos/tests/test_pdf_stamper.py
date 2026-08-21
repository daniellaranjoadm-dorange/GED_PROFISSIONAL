import hashlib
import io
from datetime import datetime

from django.test import SimpleTestCase
from pypdf import PdfReader, PdfWriter
from reportlab.pdfgen import canvas

from apps.carimbos.services.pdf_stamper import (
    PdfStampError,
    gerar_copia_controlada,
)


def pdf_teste(paginas=3):
    memoria = io.BytesIO()
    pdf = canvas.Canvas(memoria, pagesize=(400, 600))
    for numero in range(1, paginas + 1):
        pdf.drawString(40, 550, f"CONTEUDO ORIGINAL PAGINA {numero}")
        pdf.showPage()
    pdf.save()
    return memoria.getvalue()


class PdfStamperTests(SimpleTestCase):
    def test_aplica_carimbo_permanente_em_todas_as_paginas(self):
        original = pdf_teste()
        hash_original = hashlib.sha256(original).hexdigest()
        resultado = gerar_copia_controlada(
            original,
            nome_original="Procedimento CQ.pdf",
            numero_gi="GI-2026-001",
            usuario="Daniel Laranjo",
            emitido_em=datetime(2026, 7, 30, 10, 25),
        )

        self.assertEqual(hashlib.sha256(original).hexdigest(), hash_original)
        self.assertEqual(resultado.total_paginas, 3)
        self.assertEqual(
            resultado.nome_arquivo,
            "Procedimento_CQ_GI-2026-001_Daniel_Laranjo.pdf",
        )
        reader = PdfReader(io.BytesIO(resultado.conteudo))
        self.assertEqual(len(reader.pages), 3)
        for numero, pagina in enumerate(reader.pages, start=1):
            texto = pagina.extract_text()
            self.assertIn(f"CONTEUDO ORIGINAL PAGINA {numero}", texto)
            self.assertIn("CÓPIA CONTROLADA MARENOVA", texto)
            self.assertIn("GI-2026-001", texto)
            self.assertIn("Daniel Laranjo", texto)
            self.assertAlmostEqual(
                float(pagina.mediabox.height),
                600,
                places=4,
            )
            self.assertNotIn("/Annots", pagina)
        self.assertFalse(reader.get_fields())

    def test_preserva_orientacao_visual_de_pagina_rotacionada(self):
        writer = PdfWriter()
        page = writer.add_blank_page(width=400, height=600)
        page.rotate(90)
        memoria = io.BytesIO()
        writer.write(memoria)

        resultado = gerar_copia_controlada(
            memoria.getvalue(),
            nome_original="desenho.pdf",
            numero_gi="GE-001",
            usuario="Destinatário editado",
            emitido_em=datetime(2026, 8, 4, 10, 0),
            corrigir_orientacao_paisagem=True,
        )
        pagina = PdfReader(io.BytesIO(resultado.conteudo)).pages[0]

        self.assertEqual(pagina.get("/Rotate", 0), 0)
        self.assertGreater(float(pagina.mediabox.width), float(pagina.mediabox.height))

    def test_folha_de_controle_preserva_paginas_tecnicas_sem_carimbo(self):
        resultado = gerar_copia_controlada(
            pdf_teste(paginas=2),
            nome_original="desenho.pdf",
            numero_gi="GE-002",
            usuario="Transpetro",
            emitido_em=datetime(2026, 8, 4, 10, 0),
            usar_folha_controle=True,
        )
        reader = PdfReader(io.BytesIO(resultado.conteudo))

        self.assertEqual(len(reader.pages), 3)
        self.assertIn("FOLHA DE CONTROLE", reader.pages[0].extract_text())
        self.assertIn("Transpetro", reader.pages[0].extract_text())
        self.assertNotIn("CÓPIA CONTROLADA MARENOVA", reader.pages[1].extract_text())
        self.assertNotIn("CÓPIA CONTROLADA MARENOVA", reader.pages[2].extract_text())

    def test_rejeita_pdf_protegido(self):
        writer = PdfWriter()
        writer.add_blank_page(width=200, height=300)
        writer.encrypt("segredo")
        memoria = io.BytesIO()
        writer.write(memoria)
        with self.assertRaisesRegex(PdfStampError, "proteção por senha"):
            gerar_copia_controlada(
                memoria.getvalue(),
                nome_original="protegido.pdf",
                numero_gi="GI-1",
                usuario="Usuário",
                emitido_em=datetime.now(),
            )

    def test_rejeita_conteudo_invalido(self):
        with self.assertRaisesRegex(PdfStampError, "Não foi possível abrir"):
            gerar_copia_controlada(
                b"nao e pdf",
                nome_original="invalido.pdf",
                numero_gi="GI-1",
                usuario="Usuário",
                emitido_em=datetime.now(),
            )
