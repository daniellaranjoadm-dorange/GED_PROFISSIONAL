from django.contrib import admin
from django.urls import path, include
from django.conf import settings
from django.conf.urls.static import static
from django.conf.urls.i18n import set_language
from django.shortcuts import render
from apps.contas import views as contas_views

urlpatterns = [
    path("admin/", admin.site.urls),

    # 🌍 Portal público
    path("", lambda request: render(request, "contas/portal.html"), name="portal"),

    # 🔐 Login / Logout
    path("login/", contas_views.login_view, name="login"),
    path("logout/", contas_views.logout_view, name="logout"),

    # 🌐 Troca de idioma
    path("set-language/", set_language, name="set_language"),

    # Apps
    path("contas/", include(("apps.contas.urls", "contas"), namespace="contas")),
    path("documentos/", include(("apps.documentos.urls", "documentos"), namespace="documentos")),
    path("dashboard/", include(("apps.dashboard.urls", "dashboard"), namespace="dashboard")),

    # ✅ Solicitações de Acesso (IMPORTANTE: registra o namespace "solicitacoes")
    path("solicitar/", include(("apps.solicitacoes.urls", "solicitacoes"), namespace="solicitacoes")),
]

if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
