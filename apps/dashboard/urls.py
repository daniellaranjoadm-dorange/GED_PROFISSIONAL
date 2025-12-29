from django.urls import path
from . import views

app_name = "dashboard"

urlpatterns = [
    path("", views.dashboard, name="dashboard_master"),

    # Compatibilidade com o link do sidebar que está batendo em /dashboard/solicitacoes/
    path("solicitacoes/", views.solicitacoes, name="solicitacoes"),

    # Link “Usuários e Permissões” do sidebar (se existir)
    path("usuarios-permissoes/", views.usuarios_permissoes, name="usuarios_permissoes"),
]

