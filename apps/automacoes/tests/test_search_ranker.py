from django.test import SimpleTestCase

from apps.automacoes.services.search_ranker import (
    bonus_extensao,
    eh_transmittal_letter,
    ordenar_por_score,
    score_documento,
    score_match_textual,
)


class SearchRankerTests(SimpleTestCase):
    def test_score_match_exato_supera_match_parcial(self):
        exato = score_match_textual("24-7141-00-MA-001", "24-7141-00-MA-001")
        parcial = score_match_textual("MA-001", "24-7141-00-MA-001")

        self.assertGreater(exato, parcial)

    def test_bonus_extensao_prioriza_dwg_sobre_pdf(self):
        self.assertGreater(
            bonus_extensao("documento.dwg"),
            bonus_extensao("documento.pdf"),
        )

    def test_transmittal_letter_recebe_penalidade(self):
        tecnico = score_documento(
            "MA-001",
            titulo="24-7141-00-MA-001.dwg",
            caminho="24-7141-00-MA-001.dwg",
            documento_tecnico=True,
        )
        transmittal = score_documento(
            "MA-001",
            titulo="T-24-7141-00-MA-001.pdf",
            caminho="0 Transmittal Letters/T-24-7141-00-MA-001.pdf",
            eh_transmittal=True,
            documento_tecnico=False,
        )

        self.assertGreater(tecnico, transmittal)

    def test_detecta_transmittal_letter_por_nome_e_pasta(self):
        self.assertTrue(eh_transmittal_letter("0 Transmittal Letters/T-123.pdf"))
        self.assertTrue(eh_transmittal_letter("T-123.pdf"))

    def test_ordenar_por_score_ordena_decrescente(self):
        resultados = [
            {"titulo": "baixo", "score": 10},
            {"titulo": "alto", "score": 90},
            {"titulo": "medio", "score": 50},
        ]

        ordenados = ordenar_por_score(resultados)

        self.assertEqual([item["titulo"] for item in ordenados], ["alto", "medio", "baixo"])
