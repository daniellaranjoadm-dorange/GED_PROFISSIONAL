
from django.urls import path
from . import views

app_name = "dashboard"

urlpatterns = [
    # Home do dashboard (principal)
    path("", views.dashboard, name="dashboard"),
    # Alias para compatibilidade (caso algum template use dashboard:dashboard_master)
    path("", views.dashboard, name="dashboard_master"),

    # Compatibilidade com link do sidebar: /dashboard/solicitacoes/
    path("solicitacoes/", views.solicitacoes, name="solicitacoes"),

    # Link “Usuários e Permissões” do sidebar
    path("usuarios-permissoes/", views.usuarios_permissoes, name="usuarios_permissoes"),
]


