from django.contrib import admin
from django.urls import path, include
from django.conf import settings
from django.conf.urls.static import static
from django.conf.urls.i18n import set_language
from django.shortcuts import render  # ADICIONE
from apps.contas import views as contas_views

urlpatterns = [
    path("admin/", admin.site.urls),

    # 🌍 Página inicial institucional (Portal público) — agora funcionando
    path("", lambda request: render(request, "contas/portal.html"), name="portal"),

    # 🔐 Login / Logout
    path("login/", contas_views.login_view, name="login"),
    path("logout/", contas_views.logout_view, name="logout"),

    # 🌐 Suporte a troca de idioma
    path("set-language/", set_language, name="set_language"),

    # 📌 Módulos internos com namespace correto
    path("contas/", include(("apps.contas.urls", "contas"), namespace="contas")),
    path("documentos/", include(("apps.documentos.urls", "documentos"), namespace="documentos")),
    path("dashboard/", include(("apps.dashboard.urls", "dashboard"), namespace="dashboard")),
]

if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)


