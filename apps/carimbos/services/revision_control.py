from __future__ import annotations

import re
from dataclasses import dataclass

from apps.carimbos.models import DistribuicaoCopia

from .guia_parser import DadosGuia, normalizar_documento


REVISAO_SUPERIOR = 1
REVISAO_IGUAL = 0
REVISAO_INFERIOR = -1
REVISAO_INCOMPARAVEL = None


def _chave_revisao(valor: str) -> tuple[str, int] | None:
    """Converte somente as duas familias oficiais: 0..N e A..Z."""
    revisao = re.sub(r"\s+", "", str(valor or "")).upper()
    if revisao.startswith("R") and revisao[1:].isdigit():
        revisao = revisao[1:]
    if revisao.isdigit():
        return "NUMERICA", int(revisao)
    if len(revisao) == 1 and "A" <= revisao <= "Z":
        return "ALFABETICA", ord(revisao) - ord("A")
    return None


def comparar_revisoes(nova: str, anterior: str) -> int | None:
    """Retorna 1, 0, -1 ou None quando as familias nao sao comparaveis."""
    chave_nova = _chave_revisao(nova)
    chave_anterior = _chave_revisao(anterior)
    if not chave_nova or not chave_anterior or chave_nova[0] != chave_anterior[0]:
        return REVISAO_INCOMPARAVEL
    return (chave_nova[1] > chave_anterior[1]) - (
        chave_nova[1] < chave_anterior[1]
    )


@dataclass(frozen=True)
class ImpactoRevisao:
    distribuicao_id: int
    documento: str
    revisao_nova: str
    revisao_anterior: str
    destinatario: str
    email_destinatario: str
    guia_anterior: str
    emitida_em: object


@dataclass(frozen=True)
class AlertaRevisao:
    documento: str
    revisao_nova: str
    revisao_anterior: str
    guia_anterior: str
    tipo: str
    mensagem: str


@dataclass(frozen=True)
class AnaliseRevisoes:
    impactos: tuple[ImpactoRevisao, ...]
    alertas: tuple[AlertaRevisao, ...]

    @property
    def destinatarios_impactados(self) -> tuple[str, ...]:
        return tuple(dict.fromkeys(item.destinatario for item in self.impactos))


def analisar_revisoes(dados: DadosGuia) -> AnaliseRevisoes:
    impactos: list[ImpactoRevisao] = []
    alertas: list[AlertaRevisao] = []
    estados_em_poder = (
        DistribuicaoCopia.STATUS_EMITIDA,
        DistribuicaoCopia.STATUS_ENTREGUE,
        DistribuicaoCopia.STATUS_RECOLHIMENTO_PENDENTE,
    )

    for documento in dados.documentos:
        registros = (
            DistribuicaoCopia.objects.select_related("guia")
            .filter(
                documento_normalizado=normalizar_documento(documento.numero),
                status__in=estados_em_poder,
            )
            .order_by("destinatario", "-emitida_em")
        )
        for registro in registros:
            comparacao = comparar_revisoes(documento.revisao, registro.revisao)
            if comparacao == REVISAO_SUPERIOR:
                impactos.append(
                    ImpactoRevisao(
                        distribuicao_id=registro.pk,
                        documento=documento.numero,
                        revisao_nova=documento.revisao,
                        revisao_anterior=registro.revisao,
                        destinatario=registro.destinatario,
                        email_destinatario=registro.email_destinatario,
                        guia_anterior=registro.guia.numero,
                        emitida_em=registro.emitida_em,
                    )
                )
            elif comparacao == REVISAO_INFERIOR:
                alertas.append(
                    AlertaRevisao(
                        documento=documento.numero,
                        revisao_nova=documento.revisao,
                        revisao_anterior=registro.revisao,
                        guia_anterior=registro.guia.numero,
                        tipo="RETROCESSO",
                        mensagem="A revisao recebida e inferior a uma revisao ja distribuida.",
                    )
                )
            elif comparacao is REVISAO_INCOMPARAVEL:
                alertas.append(
                    AlertaRevisao(
                        documento=documento.numero,
                        revisao_nova=documento.revisao,
                        revisao_anterior=registro.revisao,
                        guia_anterior=registro.guia.numero,
                        tipo="INCOMPARAVEL",
                        mensagem="Revisoes numericas e alfabeticas exigem conferencia manual.",
                    )
                )

    return AnaliseRevisoes(tuple(impactos), tuple(alertas))
