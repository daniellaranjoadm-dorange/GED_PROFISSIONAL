from django.urls import path
from . import views

urlpatterns = [
    # Formulário público
    path("", views.solicitar_acesso_view, name="solicitar_acesso"),

    # Sucesso
    path("sucesso/", views.solicitar_acesso_sucesso, name="solicitar_acesso_sucesso"),

    # Administração de solicitações (somente staff)
    path("lista/", views.listar_solicitacoes, name="listar_solicitacoes"),

    # Detalhe e tratamento (aprovar / negar)
    path("detalhe/<int:id>/", views.detalhe_solicitacao, name="detalhe_solicitacao"),
]