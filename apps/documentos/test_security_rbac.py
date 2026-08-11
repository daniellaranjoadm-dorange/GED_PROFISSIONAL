from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse

from apps.contas.models import Role, RolePermission, UserRole
from apps.contas.permissions import usuario_tem_permissao


class GEDConsultaSecurityTests(TestCase):
    def setUp(self):
        self.user = get_user_model().objects.create_user(
            username="consulta.ged", password="senha-forte-123"
        )
        role = Role.objects.create(nome="TESTE_CONSULTA_GED")
        for code in ("ged.visualizar", "copias.visualizar"):
            RolePermission.objects.create(role=role, codigo=code)
        UserRole.objects.create(user=self.user, role=role)
        self.client.force_login(self.user)

    def test_consulta_visualiza_lista_sem_acoes_de_mutacao_no_menu(self):
        self.assertFalse(usuario_tem_permissao(self.user, "documento.criar"))
        response = self.client.get(reverse("documentos:listar_documentos"))
        self.assertEqual(response.status_code, 200)
        self.assertNotContains(response, "Novo Documento")
        self.assertNotContains(response, "Importar LDP")
        self.assertNotContains(response, "Processar GI / GE")
        self.assertNotContains(response, "Lixeira")

    def test_consulta_nao_abre_upload(self):
        self.assertEqual(self.client.get(reverse("documentos:upload_documento")).status_code, 302)

    def test_consulta_nao_importa_ldp_por_url_direta(self):
        self.assertEqual(self.client.post(reverse("documentos:importar_ldp"), {}).status_code, 302)

    def test_consulta_nao_exclui_documentos_em_lote(self):
        self.assertEqual(self.client.post(reverse("documentos:excluir_selecionados"), {}).status_code, 302)

    def test_consulta_nao_acessa_configuracoes_administrativas(self):
        self.assertEqual(self.client.get(reverse("documentos:configuracoes")).status_code, 302)
