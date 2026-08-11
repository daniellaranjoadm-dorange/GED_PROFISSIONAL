from pathlib import Path

from django.template import TemplateSyntaxError
from django.template.loader import get_template
from django.contrib.auth import get_user_model
from django.test import SimpleTestCase, TestCase
from django.urls import reverse

from .models import Role, RolePermission, UserRole
from .rbac_catalog import PERFIS_OPERACIONAIS


class PortalTemplateTests(SimpleTestCase):
    def test_portal_template_compiles_without_duplicate_sidebar_block(self):
        try:
            get_template("contas/portal.html")
        except TemplateSyntaxError as exc:
            self.fail(f"portal template should compile without syntax errors: {exc}")

    def test_portal_template_has_single_sidebar_block_declaration(self):
        template_path = Path(__file__).resolve().parent / "templates" / "contas" / "portal.html"
        source = template_path.read_text(encoding="utf-8")
        self.assertLessEqual(source.count("{% block sidebar %}"), 1)

    def test_root_route_redirects_to_enterprise_painel(self):
        response = self.client.get("/")
        self.assertEqual(response.status_code, 302)
        self.assertEqual(response["Location"], "/automacoes/")


class UsuariosPermissoesTests(TestCase):
    def setUp(self):
        User = get_user_model()
        self.admin = User.objects.create_user(
            username="gestor_acessos", password="testpass123", is_master=True
        )
        self.usuario = User.objects.create_user(
            username="colaborador", password="testpass123"
        )
        self.master_alvo = User.objects.create_superuser(
            username="master_alvo", password="testpass123", email="master@example.com"
        )
        self.consulta = Role.objects.create(nome="CONSULTA_TESTE", descricao="Somente leitura")
        self.operador = Role.objects.create(nome="OPERADOR_TESTE", descricao="Executa rotinas")

    def test_usuario_sem_permissao_nao_acessa_central(self):
        self.client.force_login(self.usuario)
        response = self.client.get(reverse("contas:usuarios_permissoes"))
        self.assertEqual(response.status_code, 302)

    def test_master_visualiza_central(self):
        self.client.force_login(self.admin)
        response = self.client.get(reverse("contas:usuarios_permissoes"))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Usuários e Permissões")
        self.assertContains(response, "colaborador")

    def test_master_atribui_perfis_ao_colaborador(self):
        self.client.force_login(self.admin)
        response = self.client.post(reverse("contas:usuarios_permissoes"), {
            "usuario_id": self.usuario.pk,
            "roles": [self.consulta.pk, self.operador.pk],
        })
        self.assertEqual(response.status_code, 302)
        self.assertSetEqual(
            set(UserRole.objects.filter(user=self.usuario).values_list("role_id", flat=True)),
            {self.consulta.pk, self.operador.pk},
        )

    def test_nao_permite_alterar_proprio_acesso(self):
        self.client.force_login(self.admin)
        self.client.post(reverse("contas:usuarios_permissoes"), {
            "usuario_id": self.admin.pk, "roles": [self.consulta.pk],
        })
        self.assertFalse(UserRole.objects.filter(user=self.admin).exists())

    def test_nao_permite_alterar_superusuario(self):
        self.client.force_login(self.admin)
        self.client.post(reverse("contas:usuarios_permissoes"), {
            "usuario_id": self.master_alvo.pk, "roles": [self.consulta.pk],
        })
        self.assertFalse(UserRole.objects.filter(user=self.master_alvo).exists())

    def test_admin_nao_superusuario_nao_pode_atribuir_master(self):
        master_role, _ = Role.objects.get_or_create(nome="MASTER", defaults={"descricao": "Acesso total"})
        self.client.force_login(self.admin)
        self.client.post(reverse("contas:usuarios_permissoes"), {
            "usuario_id": self.usuario.pk, "roles": [master_role.pk],
        })
        self.assertFalse(UserRole.objects.filter(user=self.usuario, role=master_role).exists())

    def test_arquivo_tecnico_aparece_com_permissoes_operacionais_seguras(self):
        self.assertIn("ARQUIVO_TECNICO", PERFIS_OPERACIONAIS)
        role = Role.objects.get(nome="ARQUIVO_TECNICO")
        codigos = set(
            RolePermission.objects.filter(role=role).values_list("codigo", flat=True)
        )
        self.assertTrue({"ged.visualizar", "documento.criar", "documento.editar", "copias.operar"} <= codigos)
        self.assertFalse(
            {"documento.aprovar", "documento.emitir", "documento.excluir", "administracao.gerenciar"}
            & codigos
        )
