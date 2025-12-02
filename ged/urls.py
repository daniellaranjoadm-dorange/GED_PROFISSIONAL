from django.contrib import admin
from django.urls import path, include
from django.conf import settings
from django.conf.urls.static import static
from django.shortcuts import redirect

urlpatterns = [
    path('admin/', admin.site.urls),

    # 🔥 Atalhos globais para login/logout
    path("login/", lambda request: redirect("contas:login")),
    path("logout/", lambda request: redirect("contas:logout")),

    # Documentos
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

    path("i18n/", include("django.conf.urls.i18n")),
]

if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
