from django.core.mail import send_mail
from django.conf import settings


def enviar_email(assunto, mensagem, destinatarios, html=False):
    """
    Função geral para enviar emails do sistema GED.
    
    destinatarios → lista de emails
    html → enviar como HTML (True/False)
    """

    if not isinstance(destinatarios, (list, tuple)):
        destinatarios = [destinatarios]

    try:
        if html:
            send_mail(
                assunto,
                "",
                settings.DEFAULT_FROM_EMAIL,
                destinatarios,
                html_message=mensagem,
            )
        else:
            send_mail(
                assunto,
                mensagem,
                settings.DEFAULT_FROM_EMAIL,
                destinatarios,
            )

        return True

    except Exception as e:
        print("Erro ao enviar email:", e)
        return False
