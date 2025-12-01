# Conteúdo original será atualizado automaticamente aqui.
from django.contrib import admin
from django.urls import path, include
from django.conf import settings
from django.conf.urls.static import static
from django.conf.urls.i18n import i18n_patterns  # multilíngue

urlpatterns = [
    path('admin/', admin.site.urls),

    # Documentos
    path("", include("apps.documentos.urls")),

    # Contas
    path(
        "contas/",
        include(("apps.contas.urls", "contas"), namespace="contas")
    ),

    # Solicitações
    path(
        "solicitacoes/",
        include("apps.solicitacoes.urls")
    ),

    # Dashboard
    path("dashboard/", include("apps.dashboard.urls")),
]

# rota multilíngue
urlpatterns += [
    path('i18n/', include('django.conf.urls.i18n')),
]

if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
