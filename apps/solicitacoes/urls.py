from django.urls import path
from . import views

app_name = "solicitacoes"

urlpatterns = [
    path("", views.solicitar_acesso_view, name="solicitar_acesso"),
    path("sucesso/", views.solicitar_acesso_sucesso, name="solicitar_acesso_sucesso"),
    path("lista/", views.listar_solicitacoes, name="listar_solicitacoes"),
    path("detalhe/<int:id>/", views.detalhe_solicitacao, name="detalhe_solicitacao"),
]

