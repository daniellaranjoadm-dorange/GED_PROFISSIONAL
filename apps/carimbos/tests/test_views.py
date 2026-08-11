import io

from django.contrib.auth import get_user_model
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase
from django.urls import reverse
from reportlab.pdfgen import canvas
from apps.contas.models import Role, RolePermission, UserRole


def pdf_upload():
    memoria = io.BytesIO()
    pdf = canvas.Canvas(memoria, pagesize=(300, 400))
    pdf.drawString(30, 350, "Documento para teste")
    pdf.save()
    return SimpleUploadedFile(
        "documento.pdf",
        memoria.getvalue(),
        content_type="application/pdf",
    )


class CriarCopiaControladaViewTests(TestCase):
    def setUp(self):
        self.url = reverse("carimbos:criar")
        self.usuario = get_user_model().objects.create_user(
            username="daniel.teste",
            password="senha-forte-123",
            first_name="Daniel",
            last_name="Laranjo",
        )
        role = Role.objects.create(nome="TESTE_OPERADOR_COPIAS")
        RolePermission.objects.create(role=role, codigo="copias.operar")
        UserRole.objects.create(user=self.usuario, role=role)

    def test_exige_login(self):
        response = self.client.get(self.url)
        self.assertEqual(response.status_code, 302)

    def test_predefine_nome_do_usuario_mas_permite_edicao(self):
        self.client.force_login(self.usuario)
        response = self.client.get(self.url)
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'value="Daniel Laranjo"')

    def test_gera_download_com_gi_e_usuario_informados(self):
        self.client.force_login(self.usuario)
        response = self.client.post(
            self.url,
            {
                "numero_gi": "GI-009",
                "usuario": "Usuário de Campo",
                "arquivo_pdf": pdf_upload(),
            },
        )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response["Content-Type"], "application/pdf")
        self.assertIn("COPIA_CONTROLADA_GI_GI-009.pdf", response["Content-Disposition"])
        self.assertTrue(response.content.startswith(b"%PDF-"))


class CopiasControladasRBACViewTests(TestCase):
    def setUp(self):
        self.consulta = get_user_model().objects.create_user(
            username="consulta.copias", password="senha-forte-123"
        )
        role = Role.objects.create(nome="TESTE_CONSULTA_COPIAS")
        RolePermission.objects.create(role=role, codigo="copias.visualizar")
        UserRole.objects.create(user=self.consulta, role=role)
        self.client.force_login(self.consulta)

    def test_consulta_nao_acessa_tela_de_processamento_gi(self):
        self.assertEqual(self.client.get(reverse("carimbos:guias")).status_code, 302)

    def test_consulta_nao_processa_gi_por_url_direta(self):
        response = self.client.post(reverse("carimbos:processar_guia"), {"guia": "GI-TESTE"})
        self.assertEqual(response.status_code, 302)

    def test_consulta_pode_ver_rastreabilidade(self):
        self.assertEqual(self.client.get(reverse("carimbos:rastreabilidade")).status_code, 200)
