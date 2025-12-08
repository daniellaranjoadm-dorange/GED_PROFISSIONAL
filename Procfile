release: python manage.py migrate && python create_superuser.py
web: gunicorn ged.wsgi:application --log-file -
