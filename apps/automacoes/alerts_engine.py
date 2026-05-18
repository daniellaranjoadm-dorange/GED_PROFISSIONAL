"""
Alert Engine documental.

Primeira versão sem migrations:
gera alertas dinâmicos a partir de DocumentoKM, DocumentoLD e TransmittalKM.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from django.db.models import Q

from apps.automacoes.models import DocumentoKM, DocumentoLD, TransmittalKM


@dataclass
class AlertaOperacional:
    severidade: str
    codigo: str
    titulo: str
    descricao: str
    origem: str
    referencia: str = ""
    disciplina: str = ""
    responsavel: str = ""
    url: str = ""

    def as_dict(self) -> dict[str, Any]:
        return {
            "severidade": self.severidade,
            "codigo": self.codigo,
            "titulo": self.titulo,
            "descricao": self.descricao,
            "origem": self.origem,
            "referencia": self.referencia,
            "disciplina": self.disciplina,
            "responsavel": self.responsavel,
            "url": self.url,
        }


def _texto(valor: Any) -> str:
    return str(valor or "").strip()


def _model_has_field(model, nome: str) -> bool:
    return any(field.name == nome for field in model._meta.get_fields())


def _alertas_documentokm(limite: int) -> list[AlertaOperacional]:
    alertas: list[AlertaOperacional] = []

    sem_vinculo = DocumentoKM.objects.filter(
        Q(documento_ld__isnull=True)
        | Q(status_vinculo_ld__in=[
            DocumentoKM.STATUS_VINCULO_LD_PENDENTE,
            DocumentoKM.STATUS_VINCULO_LD_SEM_MATCH,
            DocumentoKM.STATUS_VINCULO_LD_CONFLITO,
            DocumentoKM.STATUS_VINCULO_LD_MULTIPLO,
        ])
    ).order_by("numero_km")[:limite]

    for doc in sem_vinculo:
        severidade = "alta" if doc.status_vinculo_ld in {
            DocumentoKM.STATUS_VINCULO_LD_CONFLITO,
            DocumentoKM.STATUS_VINCULO_LD_MULTIPLO,
        } else "media"

        alertas.append(
            AlertaOperacional(
                severidade=severidade,
                codigo="KM_SEM_VINCULO_LD",
                titulo="Documento KM sem vínculo LD consolidado",
                descricao=f"Status vínculo: {doc.status_vinculo_ld or 'pendente'}.",
                origem="DocumentoKM",
                referencia=doc.numero_km,
                disciplina=doc.disciplina,
                responsavel=doc.responsible,
            )
        )

    pendentes = DocumentoKM.objects.filter(
        status_recebimento=DocumentoKM.STATUS_RECEBIMENTO_PENDENTE
    ).order_by("numero_km")[:limite]

    for doc in pendentes:
        alertas.append(
            AlertaOperacional(
                severidade="media",
                codigo="KM_RECEBIMENTO_PENDENTE",
                titulo="Documento KM pendente de recebimento",
                descricao="Documento consta na lista mestre KM, mas ainda não foi marcado como recebido.",
                origem="DocumentoKM",
                referencia=doc.numero_km,
                disciplina=doc.disciplina,
                responsavel=doc.responsible,
            )
        )

    score_baixo = DocumentoKM.objects.filter(
        score_vinculo_ld__gt=0,
        score_vinculo_ld__lt=70,
    ).order_by("score_vinculo_ld", "numero_km")[:limite]

    for doc in score_baixo:
        alertas.append(
            AlertaOperacional(
                severidade="media",
                codigo="KM_SCORE_BAIXO",
                titulo="Score de vínculo KM ↔ LD baixo",
                descricao=f"Score atual: {doc.score_vinculo_ld}.",
                origem="DocumentoKM",
                referencia=doc.numero_km,
                disciplina=doc.disciplina,
                responsavel=doc.responsible,
            )
        )

    return alertas


def _alertas_documentold(limite: int) -> list[AlertaOperacional]:
    alertas: list[AlertaOperacional] = []

    if _model_has_field(DocumentoLD, "status_revisao_km"):
        divergentes = DocumentoLD.objects.filter(
            status_revisao_km__iexact="DIVERGENTE"
        ).order_by("documento")[:limite]

        for doc in divergentes:
            alertas.append(
                AlertaOperacional(
                    severidade="alta",
                    codigo="LD_REVISAO_DIVERGENTE",
                    titulo="Revisão KM divergente da LD",
                    descricao="Revisão documental inconsistente entre KM e Petrobras/Transpetro.",
                    origem="DocumentoLD",
                    referencia=_texto(getattr(doc, "documento", "")),
                    disciplina=_texto(getattr(doc, "disciplina", "")),
                )
            )

    if _model_has_field(DocumentoLD, "numero_documento_km"):
        sem_km = DocumentoLD.objects.filter(
            Q(numero_documento_km="")
            | Q(numero_documento_km__isnull=True)
        ).order_by("documento")[:limite]

        for doc in sem_km:
            alertas.append(
                AlertaOperacional(
                    severidade="baixa",
                    codigo="LD_SEM_KM",
                    titulo="LD sem número KM vinculado",
                    descricao="Registro LD ainda não possui rastreabilidade KM.",
                    origem="DocumentoLD",
                    referencia=_texto(getattr(doc, "documento", "")),
                    disciplina=_texto(getattr(doc, "disciplina", "")),
                )
            )

    return alertas


def _alertas_transmittals(limite: int) -> list[AlertaOperacional]:
    alertas: list[AlertaOperacional] = []

    sem_pdf = TransmittalKM.objects.filter(
        Q(arquivo_pdf="")
        | Q(arquivo_pdf__isnull=True)
    ).order_by("transmittal_numero", "documento")[:limite]

    for item in sem_pdf:
        alertas.append(
            AlertaOperacional(
                severidade="baixa",
                codigo="TRANS_SEM_PDF",
                titulo="Transmittal KM sem PDF original",
                descricao="Registro de transmittal sem caminho do PDF de origem.",
                origem="TransmittalKM",
                referencia=f"{item.transmittal_numero} / {item.documento}",
            )
        )

    falhas = TransmittalKM.objects.filter(status_parse__iexact="FALHA").order_by(
        "transmittal_numero",
        "documento",
    )[:limite]

    for item in falhas:
        alertas.append(
            AlertaOperacional(
                severidade="alta",
                codigo="TRANS_PARSE_FALHA",
                titulo="Falha de parse em transmittal KM",
                descricao=item.observacao_parse or "Parser sinalizou falha no registro.",
                origem="TransmittalKM",
                referencia=f"{item.transmittal_numero} / {item.documento}",
            )
        )

    return alertas


def gerar_alertas_operacionais(limite_por_tipo: int = 25) -> dict[str, Any]:
    alertas = []
    alertas.extend(_alertas_documentokm(limite_por_tipo))
    alertas.extend(_alertas_documentold(limite_por_tipo))
    alertas.extend(_alertas_transmittals(limite_por_tipo))

    prioridade = {"alta": 0, "media": 1, "baixa": 2}
    alertas.sort(key=lambda item: (prioridade.get(item.severidade, 9), item.codigo, item.referencia))

    itens = [alerta.as_dict() for alerta in alertas]

    total_alta = sum(1 for item in itens if item["severidade"] == "alta")
    total_media = sum(1 for item in itens if item["severidade"] == "media")
    total_baixa = sum(1 for item in itens if item["severidade"] == "baixa")

    return {
        "ok": True,
        "total": len(itens),
        "total_alta": total_alta,
        "total_media": total_media,
        "total_baixa": total_baixa,
        "alertas": itens,
        "health_score": max(0, 100 - (total_alta * 5) - (total_media * 2) - total_baixa),
    }
