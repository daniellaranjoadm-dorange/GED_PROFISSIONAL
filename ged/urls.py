from django.contrib import admin
from django.urls import path, include
from django.conf import settings
from django.conf.urls.static import static
from django.views.generic import RedirectView

urlpatterns = [
    path('admin/', admin.site.urls),

    # 🔥 Atalhos globais para login/logout (processados antes de tudo)
    path("login/", RedirectView.as_view(pattern_name="contas:login", permanent=False)),
    path("logout/", RedirectView.as_view(pattern_name="contas:logout", permanent=False)),

    # Contas – módulo de autenticação e acesso
    path(
        "contas/",
        include(("apps.contas.urls", "contas"), namespace="contas")
    ),

    # Documentos – rota principal do sistema
    path("", include("apps.documentos.urls")),

    # Solicitações de acesso
    path("solicitacoes/", include("apps.solicitacoes.urls")),

    # Dashboard interno
    path("dashboard/", include("apps.dashboard.urls")),

    # 🌍 Internacionalização (necessário para {% url 'set_language' %})
    path("i18n/", include("django.conf.urls.i18n")),
]

# Arquivos de mídia em modo debug
if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
