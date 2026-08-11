import io

from django.contrib.auth import get_user_model
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase
from django.urls import reverse
from reportlab.pdfgen import canvas


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
