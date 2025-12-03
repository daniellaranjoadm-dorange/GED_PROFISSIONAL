import django
from django.conf import settings

print("\n=== APPS CARREGADOS PELO DJANGO ===")
for app in settings.INSTALLED_APPS:
    print(" -", app)

print("\n=== MÓDULOS DE MODELS CARREGADOS ===")
for app in django.apps.apps.get_app_configs():
    print(f"{app.label} -> {app.module}")
