from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.contrib.auth.tokens import default_token_generator
from django.test import TestCase
from django.urls import reverse
from django.utils.encoding import force_bytes
from django.utils.http import urlsafe_base64_encode

from apps.contas.models import Role, UserRole
from .models import SolicitarAcesso


class FluxoSolicitacaoAcessoTests(TestCase):
    def setUp(self):
        User = get_user_model()
        self.master = User.objects.create_user(
            username="master_fluxo", password="testpass123", is_master=True, is_staff=True
        )
        self.role, _ = Role.objects.get_or_create(nome="CONSULTA", defaults={"descricao": "Leitura"})

    @patch("apps.solicitacoes.views.notificar_nova_solicitacao")
    def test_formulario_publico_registra_solicitacao(self, notificar):
        response = self.client.post(reverse("solicitacoes:solicitar_acesso"), {
            "nome": "Maria Engenharia", "email": "maria@example.com",
            "setor": "Engenharia", "projeto_empresa": "Marenova",
            "perfil_solicitado": self.role.pk,
            "motivo": "Necessito consultar os documentos do projeto.",
        })
        self.assertEqual(response.status_code, 302)
        self.assertTrue(SolicitarAcesso.objects.filter(email="maria@example.com").exists())
        notificar.assert_called_once()

    def test_formulario_publico_oferece_perfil_arquivo_tecnico(self):
        response = self.client.get(reverse("solicitacoes:solicitar_acesso"))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "ARQUIVO_TECNICO")

    def test_impede_solicitacao_duplicada(self):
        SolicitarAcesso.objects.create(
            nome="Maria", email="maria@example.com", motivo="Motivo suficientemente longo",
            perfil_solicitado=self.role,
        )
        response = self.client.post(reverse("solicitacoes:solicitar_acesso"), {
            "nome": "Maria", "email": "maria@example.com", "setor": "Engenharia",
            "perfil_solicitado": self.role.pk, "motivo": "Outra solicitação para o mesmo acesso",
        })
        self.assertEqual(response.status_code, 200)
        self.assertEqual(SolicitarAcesso.objects.filter(email="maria@example.com").count(), 1)

    @patch("apps.solicitacoes.views.notificar_decisao_solicitacao")
    def test_aprovacao_cria_conta_inativa_com_perfil_e_convite(self, notificar):
        solicitacao = SolicitarAcesso.objects.create(
            nome="Maria", email="maria@example.com", motivo="Consulta de documentos do projeto",
            perfil_solicitado=self.role,
        )
        self.client.force_login(self.master)
        response = self.client.post(reverse("solicitacoes:detalhe_solicitacao", args=[solicitacao.pk]), {
            "acao": "aprovar", "perfil_concedido": self.role.pk, "observacao": "Aprovado",
        })
        self.assertEqual(response.status_code, 302)
        usuario = get_user_model().objects.get(email="maria@example.com")
        self.assertFalse(usuario.is_active)
        self.assertFalse(usuario.has_usable_password())
        self.assertTrue(UserRole.objects.filter(user=usuario, role=self.role).exists())
        convite_url = notificar.call_args.args[1]
        self.assertIn("/solicitar/convite/", convite_url)

    def test_convite_define_senha_e_ativa_conta(self):
        User = get_user_model()
        usuario = User.objects.create_user(username="novo@example.com", email="novo@example.com", is_active=False)
        usuario.set_unusable_password()
        usuario.save()
        uid = urlsafe_base64_encode(force_bytes(usuario.pk))
        token = default_token_generator.make_token(usuario)
        response = self.client.post(reverse("solicitacoes:aceitar_convite", args=[uid, token]), {
            "new_password1": "SenhaForte!2026-Acesso",
            "new_password2": "SenhaForte!2026-Acesso",
        })
        self.assertEqual(response.status_code, 302)
        usuario.refresh_from_db()
        self.assertTrue(usuario.is_active)
        self.assertTrue(usuario.check_password("SenhaForte!2026-Acesso"))

    def test_arquiva_concluidas_sem_ocultar_pendentes(self):
        pendente = SolicitarAcesso.objects.create(
            nome="Pendente", email="pendente@example.com", motivo="Aguardando análise do acesso",
            perfil_solicitado=self.role,
        )
        aprovada = SolicitarAcesso.objects.create(
            nome="Aprovada", email="aprovada@example.com", motivo="Solicitação já analisada",
            status=SolicitarAcesso.STATUS_APROVADO, perfil_solicitado=self.role,
        )
        self.client.force_login(self.master)
        response = self.client.post(reverse("solicitacoes:listar_solicitacoes"), {
            "acao": "arquivar_concluidas",
        })
        self.assertEqual(response.status_code, 302)
        pendente.refresh_from_db(); aprovada.refresh_from_db()
        self.assertFalse(pendente.arquivada)
        self.assertTrue(aprovada.arquivada)
        self.assertEqual(aprovada.arquivada_por, self.master)

    def test_detalhe_concluido_nao_exibe_formulario_de_decisao(self):
        concluida = SolicitarAcesso.objects.create(
            nome="Concluída", email="concluida@example.com", motivo="Solicitação concluída",
            status=SolicitarAcesso.STATUS_APROVADO, perfil_solicitado=self.role,
        )
        self.client.force_login(self.master)
        response = self.client.get(reverse("solicitacoes:detalhe_solicitacao", args=[concluida.pk]))
        self.assertContains(response, "Solicitação já analisada")
        self.assertNotContains(response, 'name="acao" value="aprovar"')

    def test_detalhe_aprovado_exibe_convite_manual_para_conta_inativa(self):
        User = get_user_model()
        usuario = User.objects.create_user(
            username="manual@example.com", email="manual@example.com", is_active=False
        )
        usuario.set_unusable_password(); usuario.save()
        concluida = SolicitarAcesso.objects.create(
            nome="Convite Manual", email="manual@example.com", motivo="Acesso aprovado",
            status=SolicitarAcesso.STATUS_APROVADO, perfil_solicitado=self.role,
            perfil_concedido=self.role,
        )
        self.client.force_login(self.master)
        response = self.client.get(reverse("solicitacoes:detalhe_solicitacao", args=[concluida.pk]))
        self.assertContains(response, "Convite manual seguro")
        self.assertContains(response, "/solicitar/convite/")
