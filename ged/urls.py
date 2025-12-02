from django.contrib import admin
from django.urls import path, include
from django.conf import settings
from django.conf.urls.static import static
from apps.contas import views as contas_views

urlpatterns = [
    path('admin/', admin.site.urls),

    # Atalhos globais de login/logout funcionando
    path("login/", contas_views.login_view, name="login_global"),
    path("logout/", contas_views.logout_view, name="logout"),

    # Documentos – rota principal
    path("", include("apps.documentos.urls")),

    # Contas
    path(
        "contas/",
        include(("apps.contas.urls", "contas"), namespace="contas")
    ),

    # Solicitações
    path("solicitacoes/", include("apps.solicitacoes.urls")),

    # Dashboard
    path("dashboard/", include("apps.dashboard.urls")),

    # Internacionalização
    path("i18n/", include("django.conf.urls.i18n")),
]

if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
