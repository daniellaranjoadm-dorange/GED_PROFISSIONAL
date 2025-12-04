import os
import django
from django.contrib.auth import get_user_model

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "ged.settings")
django.setup()

User = get_user_model()

USERNAME = os.environ.get("ADMIN_USER", "admin")
EMAIL = os.environ.get("ADMIN_EMAIL", "admin@email.com")
PASSWORD = os.environ.get("ADMIN_PASSWORD", "admin123")

if not User.objects.filter(username=USERNAME).exists():
    User.objects.create_superuser(USERNAME, EMAIL, PASSWORD)
    print("Superusuário criado com sucesso!")
else:
    print("Superusuário já existe, nada foi feito.")
