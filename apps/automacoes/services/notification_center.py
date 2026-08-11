from datetime import date, timedelta

from django.utils import timezone

from apps.automacoes.models import DocumentoLD, ExecucaoAutomacao
from apps.automacoes.services.pcf_response_report import build_record
from apps.solicitacoes.models import SolicitarAcesso


def montar_central_notificacoes(*, incluir_acessos=False, limite=20):
    desde = timezone.now() - timedelta(days=7)
    falhas = list(
        ExecucaoAutomacao.objects.select_related("usuario")
        .filter(status=ExecucaoAutomacao.STATUS_ERRO, iniciado_em__gte=desde)
        .order_by("-iniciado_em")[:limite]
    )

    vencidas = []
    for documento in DocumentoLD.objects.exclude(pcf="").iterator(chunk_size=250):
        try:
            item = build_record(documento, today=date.today())
        except Exception:
            continue
        if item.get("situacao") == "Vencida":
            vencidas.append(item)
    vencidas.sort(key=lambda item: int(item.get("dias_atraso") or 0), reverse=True)
    vencidas = vencidas[:limite]

    acessos = []
    if incluir_acessos:
        acessos = list(
            SolicitarAcesso.objects.select_related("perfil_solicitado")
            .filter(status=SolicitarAcesso.STATUS_PENDENTE, arquivada=False)
            .order_by("data_solicitacao")[:limite]
        )

    return {
        "falhas": falhas,
        "pcfs_vencidas": vencidas,
        "acessos_pendentes": acessos,
        "total_falhas": len(falhas),
        "total_pcfs_vencidas": len(vencidas),
        "total_acessos_pendentes": len(acessos),
        "total_prioridades": len(falhas) + len(vencidas) + len(acessos),
        "inclui_acessos": incluir_acessos,
        "gerado_em": timezone.now(),
    }
