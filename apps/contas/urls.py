from django.urls import path
from . import views

app_name = "contas"

urlpatterns = [
    path("login/", views.login_view, name="login"),
    path("logout/", views.logout_view, name="logout"),

    path("minhas-configuracoes/", views.minhas_configuracoes, name="minhas_configuracoes"),

    # solicitações de acesso
    path("solicitar-acesso/", views.solicitar_acesso, name="solicitar_acesso"),
    path("painel-solicitacoes/", views.painel_solicitacoes, name="painel_solicitacoes"),

    # atalho (caso algum menu antigo use /contas/solicitacoes/)
    path("solicitacoes/", views.painel_solicitacoes, name="solicitacoes"),

    path("aprovar/<int:id>/", views.aprovar_solicitacao, name="aprovar_solicitacao"),
    path("negar/<int:id>/", views.negar_solicitacao, name="negar_solicitacao"),

    # Usuários e permissões (atalho simples)
    path("usuarios-permissoes/", views.usuarios_permissoes, name="usuarios_permissoes"),
]
