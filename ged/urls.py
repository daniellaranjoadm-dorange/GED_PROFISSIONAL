from django.contrib import admin
from django.urls import path, include
from django.conf import settings
from django.conf.urls.static import static
from apps.contas import views as contas_views

urlpatterns = [
    path("admin/", admin.site.urls),

    # LOGIN / LOGOUT
    path("login/", contas_views.login_view, name="login"),
    path("logout/", contas_views.logout_view, name="logout"),

    # ROTA PRINCIPAL DO SISTEMA
    # Agora a raiz "/" envia diretamente para a tela de login
    # (evita loops e mantém comportamento consistente)
    path("", contas_views.login_view, name="home"),

    # Contas de usuários
    path(
        "contas/",
        include(("apps.contas.urls", "contas"), namespace="contas")
    ),

    # Documentos
    path("documentos/", include("apps.documentos.urls")),

    # Solicitações
    path("solicitacoes/", include("apps.solicitacoes.urls")),

    # Dashboard
    path("dashboard/", include("apps.dashboard.urls")),

    # Internacionalização
    path("i18n/", include("django.conf.urls.i18n")),
]

# Arquivos de media só servem em DEBUG
if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
