import os
import django
import socket
import smtplib

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "ged.settings")  # ajuste se necessário
django.setup()

from django.conf import settings
from django.core.mail import EmailMessage, get_connection

print("MODO:", "DEBUG" if settings.DEBUG else "PROD")
print("EMAIL_HOST:", getattr(settings, "EMAIL_HOST", None))
print("EMAIL_PORT:", getattr(settings, "EMAIL_PORT", None))
print("EMAIL_USE_TLS:", getattr(settings, "EMAIL_USE_TLS", None))
print("EMAIL_HOST_USER:", getattr(settings, "EMAIL_HOST_USER", None))
print("DEFAULT_FROM_EMAIL:", getattr(settings, "DEFAULT_FROM_EMAIL", None))

# Timeout de rede (pra não travar)
socket.setdefaulttimeout(15)

try:
    # Conexão explícita
    connection = get_connection(
        host=settings.EMAIL_HOST,
        port=settings.EMAIL_PORT,
        username=settings.EMAIL_HOST_USER,
        password=settings.EMAIL_HOST_PASSWORD,
        use_tls=settings.EMAIL_USE_TLS,
        timeout=15,
    )

    print("Abrindo conexão SMTP...")
    connection.open()
    print("Conexão aberta ✅")

    msg = EmailMessage(
        subject="Teste GED (Cursor)",
        body="Se você recebeu, o Gmail SMTP está OK.",
        from_email=settings.DEFAULT_FROM_EMAIL,
        to=["SEU_EMAIL_DESTINO@gmail.com"],
        connection=connection,
    )

    print("Enviando...")
    sent = msg.send(fail_silently=False)
    print("Enviado ✅ retorno:", sent)

    connection.close()
    print("Conexão fechada.")

except smtplib.SMTPAuthenticationError as e:
    print("❌ AUTH ERROR (senha/app password):", e)
except Exception as e:
    print("❌ ERRO:", repr(e))

