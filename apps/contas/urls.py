from django.urls import path
from . import views

urlpatterns = [
    path("login/", views.login_view, name="login"),
    path("logout/", views.logout_view, name="logout"),
    path("minhas-configuracoes/", views.minhas_configuracoes, name="minhas_configuracoes"),

    # solicitações de acesso
    path("solicitar-acesso/", views.solicitar_acesso, name="solicitar_acesso"),
    path("painel-solicitacoes/", views.painel_solicitacoes, name="painel_solicitacoes"),
    path("aprovar/<int:id>/", views.aprovar_solicitacao, name="aprovar_solicitacao"),
    path("negar/<int:id>/", views.negar_solicitacao, name="negar_solicitacao"),
]

