from django.urls import path
from . import views

app_name = "contas"

urlpatterns = [
    path("login/", views.login_view, name="login"),
    path("logout/", views.logout_view, name="logout"),

    # Configurações do usuário
    path("minhas-configuracoes/", views.minhas_configuracoes, name="minhas_configuracoes"),

    # Solicitar acesso (página pública)
    path("solicitar-acesso/", views.solicitar_acesso, name="solicitar_acesso"),

    # Painel interno (somente master)
    path("painel-solicitacoes/", views.painel_solicitacoes, name="painel_solicitacoes"),

    # Ações
    path("solicitacoes/<int:id>/aprovar/", views.aprovar_solicitacao, name="aprovar_solicitacao"),
    path("solicitacoes/<int:id>/negar/", views.negar_solicitacao, name="negar_solicitacao"),
]
