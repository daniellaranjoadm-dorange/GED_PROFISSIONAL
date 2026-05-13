from django.test import SimpleTestCase

from apps.automacoes.services.ld_parser import extrair_tipo_documental


class LDParserTests(SimpleTestCase):
    def test_extrai_tipo_documental_padrao_ld(self):
        self.assertEqual(extrair_tipo_documental("24-7141-00-MA-001"), "MA")
        self.assertEqual(extrair_tipo_documental("24-7141-00-DE-001"), "DE")
        self.assertEqual(extrair_tipo_documental("24-7141-00-ET-001"), "ET")
        self.assertEqual(extrair_tipo_documental("24-7141-00-RL-001"), "RL")

    def test_extrai_tipo_documental_normaliza_espacos_e_minusculas(self):
        self.assertEqual(extrair_tipo_documental(" 24-7141-00-ma-001 "), "MA")

    def test_extrai_tipo_documental_retorna_vazio_quando_invalido(self):
        self.assertEqual(extrair_tipo_documental(""), "")
        self.assertEqual(extrair_tipo_documental(None), "")
        self.assertEqual(extrair_tipo_documental("DOCUMENTO SEM PADRAO"), "")
