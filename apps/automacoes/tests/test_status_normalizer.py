from django.test import SimpleTestCase

from apps.automacoes.services.status_normalizer import normalizar_status


class StatusNormalizerTests(SimpleTestCase):
    def test_normaliza_status_basicos(self):
        self.assertEqual(normalizar_status("released"), "RELEASED")
        self.assertEqual(normalizar_status(" Released "), "RELEASED")
        self.assertEqual(normalizar_status("RELEASED WITH COMMENTS"), "RELEASED WITH COMMENTS")
        self.assertEqual(normalizar_status("not released"), "NOT RELEASED")

    def test_normaliza_status_vazio(self):
        self.assertEqual(normalizar_status(None), "SEM STATUS")
        self.assertEqual(normalizar_status(""), "SEM STATUS")
        self.assertEqual(normalizar_status("   "), "SEM STATUS")

    def test_normaliza_status_na(self):
        self.assertEqual(normalizar_status("n/a"), "SEM STATUS")
        self.assertEqual(normalizar_status("NA"), "SEM STATUS")
        self.assertEqual(normalizar_status("-"), "SEM STATUS")
