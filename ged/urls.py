from django.contrib import admin
from django.urls import path, include
from django.conf import settings
from django.conf.urls.static import static

urlpatterns = [
    path("admin/", admin.site.urls),

    # ---- ROTA PRINCIPAL ----
    # Quando acessar "/", será redirecionado para documentos
    path("", include(("apps.documentos.urls", "documentos"), namespace="documentos")),

    # ---- CONTAS (login, logout) ----
    path("login/", include(("apps.contas.urls", "contas"), namespace="contas")),
]
    
# Static e media em modo debug
if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)




