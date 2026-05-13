
from apps.automacoes.models import RuntimeAlert


def obter_runtime_alertas():
    return {
        "abertos": RuntimeAlert.objects.filter(resolvido=False),
        "criticos": RuntimeAlert.objects.filter(
            resolvido=False,
            severidade=RuntimeAlert.SEVERITY_CRITICAL,
        ),
        "total_abertos": RuntimeAlert.objects.filter(resolvido=False).count(),
    }
