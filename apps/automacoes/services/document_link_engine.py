"""
Motor de vínculo documental KM ↔ LD Petrobras.

Objetivo:
- Relacionar documentos recebidos por Transmittal KM com registros da Lista LD.
- Atualizar a LD com número KM, transmittal, data de recebimento, score e status.
- Ignorar LD Marenova no vínculo automático.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable

from django.db import transaction
from django.db.models import Q

from apps.automacoes.models import DocumentoLD, KMFileIndex, TransmittalKM


def _texto(valor) -> str:
    return str(valor or "").strip()


def _normalizar_documento(valor) -> str:
    texto = _texto(valor).upper()
    texto = texto.replace("\\", "/").split("/")[-1]
    texto = texto.split(".", 1)[0]
    texto = texto.replace("_", "-")
    texto = " ".join(texto.split())
    return texto.strip()


def _compactar(valor) -> str:
    return "".join(ch for ch in _normalizar_documento(valor) if ch.isalnum())


def _tokens(valor) -> list[str]:
    texto = _normalizar_documento(valor)
    atual = []
    tokens = []

    for ch in texto:
        if ch.isalnum():
            atual.append(ch)
        elif atual:
            tokens.append("".join(atual))
            atual = []

    if atual:
        tokens.append("".join(atual))

    return [token for token in tokens if token]


def _origem_ld_petroleo_q():
    """
    Regra operacional:
    - participa do vínculo: aba LD e registros sem origem antiga;
    - não participa: LD Marenova.
    """
    return (
        Q(origem_aba__isnull=True)
        | Q(origem_aba="")
        | Q(origem_aba__iexact="LD")
        | Q(origem_aba__iexact="Lista LD")
        | Q(origem_aba__icontains="LD")
    ) & ~Q(origem_aba__icontains="Marenova")


def _score_match(numero_km: str, item_ld: DocumentoLD) -> int:
    km_norm = _normalizar_documento(numero_km)
    km_compacto = _compactar(numero_km)
    km_tokens = _tokens(numero_km)

    campos = [
        item_ld.numero_documento_km,
        item_ld.documento,
        item_ld.titulo,
        item_ld.caminho_documento,
        item_ld.caminho_grd,
        item_ld.caminho_pcf,
        item_ld.caminho_resposta,
        item_ld.caminho_grd_resposta,
    ]

    melhor = 0

    for valor in campos:
        texto = _texto(valor)
        if not texto:
            continue

        texto_norm = _normalizar_documento(texto)
        texto_compacto = _compactar(texto)

        if texto_norm == km_norm:
            melhor = max(melhor, 100)

        if km_compacto and texto_compacto == km_compacto:
            melhor = max(melhor, 98)

        if km_norm and km_norm in texto_norm:
            melhor = max(melhor, 88)

        if km_compacto and km_compacto in texto_compacto:
            melhor = max(melhor, 84)

        if texto_compacto and texto_compacto in km_compacto and len(texto_compacto) >= 8:
            melhor = max(melhor, 70)

        if km_tokens and all(token in texto_norm for token in km_tokens):
            melhor = max(melhor, 68)

        if km_tokens and all(token in texto_compacto for token in km_tokens):
            melhor = max(melhor, 64)

    return min(melhor, 100)


def _arquivo_km_existe(numero_km: str) -> bool:
    compacto = _compactar(numero_km)

    if not compacto:
        return False

    return KMFileIndex.objects.filter(
        ativo=True,
    ).filter(
        Q(nome_normalizado__icontains=compacto)
        | Q(stem_normalizado__icontains=compacto)
        | Q(documento_extraido__icontains=_texto(numero_km))
    ).exists()


@dataclass
class ResultadoVinculo:
    processados: int = 0
    vinculados_auto: int = 0
    pendentes: int = 0
    multiplos: int = 0
    conflitos: int = 0
    sem_match: int = 0
    ignorados: int = 0

    def as_dict(self) -> dict:
        return {
            "processados": self.processados,
            "vinculados_auto": self.vinculados_auto,
            "pendentes": self.pendentes,
            "multiplos": self.multiplos,
            "conflitos": self.conflitos,
            "sem_match": self.sem_match,
            "ignorados": self.ignorados,
        }


class DocumentLinkEngine:
    """
    Serviço de vínculo automático KM ↔ LD.

    Fase 1:
    - Não cria tabela nova.
    - Atualiza diretamente DocumentoLD.
    - Mantém vínculo somente para LD Petrobras/Transpetro.
    """

    SCORE_AUTO = 90
    SCORE_PENDENTE = 60

    def __init__(self, limite_candidatos: int = 300):
        self.limite_candidatos = limite_candidatos

    def executar(self) -> ResultadoVinculo:
        resultado = ResultadoVinculo()

        transmittals = (
            TransmittalKM.objects.exclude(documento="")
            .order_by("documento", "-criado_em")
        )

        for registro in transmittals.iterator(chunk_size=500):
            resultado.processados += 1
            self._processar_registro(registro, resultado)

        return resultado

    def _buscar_candidatos_ld(self, numero_km: str) -> list[DocumentoLD]:
        numero = _texto(numero_km)
        numero_norm = _normalizar_documento(numero)
        numero_compacto = _compactar(numero)

        if not numero:
            return []

        base = DocumentoLD.objects.filter(_origem_ld_petroleo_q())

        # 1) Match direto no campo oficial KM.
        diretos = list(
            base.filter(numero_documento_km__iexact=numero)
            .order_by("-atualizado_em")[: self.limite_candidatos]
        )
        if diretos:
            return diretos

        # 2) Busca textual em campos relevantes.
        busca_q = (
            Q(documento__icontains=numero_norm)
            | Q(titulo__icontains=numero_norm)
            | Q(numero_documento_km__icontains=numero_norm)
            | Q(caminho_documento__icontains=numero_norm)
            | Q(caminho_grd__icontains=numero_norm)
            | Q(caminho_pcf__icontains=numero_norm)
            | Q(caminho_resposta__icontains=numero_norm)
            | Q(caminho_grd_resposta__icontains=numero_norm)
        )

        candidatos = list(
            base.filter(busca_q).order_by("-atualizado_em")[: self.limite_candidatos]
        )

        if candidatos:
            return candidatos

        # 3) Fallback controlado por documento compacto.
        # Evita varrer a LD inteira em produção.
        fallback = list(
            base.exclude(documento="")
            .order_by("-atualizado_em")[: self.limite_candidatos]
        )

        filtrados = []
        for item in fallback:
            campos = [
                item.documento,
                item.titulo,
                item.numero_documento_km,
                item.caminho_documento,
            ]
            if any(numero_compacto and numero_compacto in _compactar(campo) for campo in campos):
                filtrados.append(item)

        return filtrados

    @transaction.atomic
    def _processar_registro(self, registro: TransmittalKM, resultado: ResultadoVinculo) -> None:
        numero_km = _texto(registro.documento)

        if not numero_km:
            resultado.ignorados += 1
            return

        candidatos = self._buscar_candidatos_ld(numero_km)

        if not candidatos:
            resultado.sem_match += 1
            return

        pontuados = [
            (_score_match(numero_km, item), item)
            for item in candidatos
        ]
        pontuados = [(score, item) for score, item in pontuados if score > 0]
        pontuados.sort(key=lambda par: par[0], reverse=True)

        if not pontuados:
            resultado.sem_match += 1
            return

        melhor_score, melhor_item = pontuados[0]
        segundo_score = pontuados[1][0] if len(pontuados) > 1 else 0

        if melhor_score >= self.SCORE_AUTO and segundo_score >= self.SCORE_AUTO and melhor_score == segundo_score:
            status = DocumentoLD.STATUS_VINCULO_KM_MULTIPLO
            resultado.multiplos += 1
        elif melhor_score >= self.SCORE_AUTO:
            status = DocumentoLD.STATUS_VINCULO_KM_AUTO
            resultado.vinculados_auto += 1
        elif melhor_score >= self.SCORE_PENDENTE:
            status = DocumentoLD.STATUS_VINCULO_KM_PENDENTE
            resultado.pendentes += 1
        else:
            status = DocumentoLD.STATUS_VINCULO_KM_SEM_MATCH
            resultado.sem_match += 1

        melhor_item.numero_documento_km = numero_km
        melhor_item.transmittal_km = _texto(registro.transmittal_numero)
        melhor_item.data_recebimento_km = _texto(registro.data_envio)
        melhor_item.arquivo_km_encontrado = _arquivo_km_existe(numero_km)
        melhor_item.status_vinculo_km = status
        melhor_item.score_vinculo_km = int(melhor_score)
        melhor_item.observacao_vinculo_km = (
            f"Vínculo atualizado pelo DocumentLinkEngine. "
            f"KM={numero_km}; Transmittal={registro.transmittal_numero or '-'}; "
            f"Score={melhor_score}; Segundo score={segundo_score}."
        )

        melhor_item.save(
            update_fields=[
                "numero_documento_km",
                "transmittal_km",
                "data_recebimento_km",
                "arquivo_km_encontrado",
                "status_vinculo_km",
                "score_vinculo_km",
                "observacao_vinculo_km",
                "atualizado_em",
            ]
        )


def executar_vinculo_km_ld() -> dict:
    resultado = DocumentLinkEngine().executar()
    dados = resultado.as_dict()

    return {
        "ok": True,
        "mensagem": (
            "Vínculo KM ↔ LD executado: "
            f"{dados['vinculados_auto']} automáticos, "
            f"{dados['pendentes']} pendentes, "
            f"{dados['sem_match']} sem match."
        ),
        "quantidade_processada": dados["processados"],
        "detalhes": dados,
    }
