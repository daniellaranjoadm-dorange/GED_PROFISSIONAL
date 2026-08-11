from pathlib import Path

from django.test import SimpleTestCase

from apps.automacoes.services.transmittal_km import extrair_registros_pdf


class TransmittalKMParserTests(SimpleTestCase):
    def test_extracts_all_documents_with_hyphen_and_dot_numbering(self):
        texto = """
Document Transmittal Report
Transmittal number: 45946
Document Information Yard Delivery Owner Delivery Version
630-051-Det. Assembly stern tube.dwg (3.13 Outfitting)
Comment: First issue Send for Approval Send for Approval 1.0
263-433.100.01-Support for mooring equipment - Midship.dwg (3.4 Steel Class & Main Structures)
Comment: First issue Send for Approval Send for Approval 1.0
Transmittal System Link:
Sent By: Sinisa Tomic, 29.07.2026
"""

        registros = extrair_registros_pdf(
            texto,
            "T-45946-Outfitting and Foundation drawings.pdf",
            Path("T-45946.pdf"),
        )

        self.assertEqual(len(registros), 2)
        self.assertEqual(
            [registro["Documento"] for registro in registros],
            ["630-051", "263-433.100.01"],
        )
        self.assertEqual(
            [registro["Titulo"] for registro in registros],
            [
                "Det. Assembly stern tube.dwg",
                "Support for mooring equipment - Midship.dwg",
            ],
        )
        transmittals = [
            next(
                valor
                for chave, valor in registro.items()
                if chave.startswith("Transmittal N")
            )
            for registro in registros
        ]
        self.assertEqual(transmittals, ["T-45946", "T-45946"])
        self.assertTrue(
            all(registro["Data Envio"] == "29/07/2026" for registro in registros)
        )
