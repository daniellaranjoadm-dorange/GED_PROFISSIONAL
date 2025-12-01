import os

# CONFIGURA O DJANGO ANTES DE TUDO
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "ged.settings")

import django
django.setup()

from django.db import connection

cursor = connection.cursor()
cursor.execute("DELETE FROM django_migrations WHERE app = 'contas';")
connection.commit()

print("OK — migrations apagadas da tabela django_migrations")
