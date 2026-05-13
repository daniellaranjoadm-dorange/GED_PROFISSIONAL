
from apps.automacoes.models import RuntimeAlert


def enviar_notificacao_console(alerta: RuntimeAlert):
    print(
        f"[{alerta.severidade}] "
        f"{alerta.codigo} :: "
        f"{alerta.job_name} :: "
        f"{alerta.mensagem}"
    )
    return True


def processar_alertas_pendentes(limit=20):
    alertas = RuntimeAlert.objects.filter(
        resolvido=False
    ).order_by("-criado_em")[:limit]

    enviados = 0

    for alerta in alertas:
        enviar_notificacao_console(alerta)
        enviados += 1

    return enviados
