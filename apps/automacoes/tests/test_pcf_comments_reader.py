import os
import tempfile
from datetime import date, datetime

from django.test import SimpleTestCase
from openpyxl import Workbook

from apps.automacoes.services.atualizar_ld_projeto_basico import (
    _pcf_data_documental_arquivo,
    _pcf_qtd_e_open_comments_timeline,
)


class PCFCommentsReaderTests(SimpleTestCase):
    def test_uses_latest_open_comments_from_pcf_history(self):
        ws = Workbook().active
        ws["A1"] = "PCF History"
        ws["A3"] = "Round"
        ws["H3"] = "Open Comments"
        ws["A4"], ws["H4"] = "a)", 16
        ws["A5"], ws["H5"] = "b)", 19
        ws["A6"], ws["H6"] = "c)", 3

        ws["J12"] = "Comment Status"
        for row in range(13, 46):
            ws.cell(row, 10).value = "OPEN" if row < 29 else "CLOSED"

        total, open_comments, under_review = (
            _pcf_qtd_e_open_comments_timeline(ws)
        )

        self.assertEqual(total, 33)
        self.assertEqual(open_comments, 3)
        self.assertEqual(under_review, 0)

    def test_falls_back_to_detailed_status_count_without_history(self):
        ws = Workbook().active
        ws["C2"] = "Comment Status"
        ws["C3"] = "OPEN"
        ws["C4"] = "CLOSED"
        ws["C5"] = "OPEN"
        ws["C6"] = "UNDER REVIEW"

        total, open_comments, under_review = (
            _pcf_qtd_e_open_comments_timeline(ws)
        )

        self.assertEqual(total, 4)
        self.assertEqual(open_comments, 2)
        self.assertEqual(under_review, 1)

    def test_accepts_zero_as_latest_history_balance(self):
        ws = Workbook().active
        ws["A1"] = "PCF History"
        ws["A3"] = "Round"
        ws["H3"] = "Open Comments"
        ws["A4"], ws["H4"] = "a)", 5
        ws["A5"], ws["H5"] = "b)", 0
        ws["J12"] = "Comment Status"
        ws["J13"] = "OPEN"

        _, open_comments, _ = _pcf_qtd_e_open_comments_timeline(ws)

        self.assertEqual(open_comments, 0)

    def test_parses_composite_balance_from_latest_history_round(self):
        ws = Workbook().active
        ws["A1"] = "PCF History"
        ws["A3"] = "Round"
        ws["J3"] = "Open Comments"
        ws["A4"], ws["J4"] = "a)", 15
        ws["A5"], ws["J5"] = "b)", 7
        ws["A6"], ws["J6"] = "c)", "2 OPEN, 4 UNDER REVIEW"
        ws["L10"] = "Comment Status"
        for row, status in enumerate(
            ["OPEN"] * 7 + ["UNDER REVIEW"] * 4 + ["CLOSED"] * 4,
            start=11,
        ):
            ws.cell(row, 12).value = status

        total, open_comments, under_review = (
            _pcf_qtd_e_open_comments_timeline(ws)
        )

        self.assertEqual(total, 15)
        self.assertEqual(open_comments, 2)
        self.assertEqual(under_review, 4)

    def test_reads_document_date_from_pcf_header(self):
        wb = Workbook()
        ws = wb.active
        ws["K5"] = "Date"
        ws["L5"] = datetime(2026, 2, 25)

        handle, caminho = tempfile.mkstemp(suffix=".xlsx")
        os.close(handle)
        try:
            wb.save(caminho)
            self.assertEqual(
                _pcf_data_documental_arquivo(caminho),
                date(2026, 2, 25),
            )
        finally:
            wb.close()
            os.unlink(caminho)
