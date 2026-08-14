from django.db.models import Max, Q
from django.utils import timezone

from apps.automacoes.models import (
    DocumentoLD,
    ExecutiveMetricSnapshot,
    ExecucaoAutomacao,
    PCFTimeline,
    TransmittalKM,
)
from apps.automacoes.services.ld_executive_intelligence import montar_inteligencia_executiva
from apps.documentos.models import DocumentoReferenciaExterna


def _pct(numerador, denominador):
    return round((numerador / denominador) * 100, 1) if denominador else 100.0


def qualidade_dados_executiva(registros):
    ids = list(registros.values_list("id", flat=True))
    base = DocumentoLD.objects.filter(id__in=ids)
    total = base.count()
    vinculados = base.exclude(documento_ged=None).count()
    responsaveis = base.exclude(resp_for_issue="").count()
    cronograma = base.exclude(cronograma_termino="").count()
    arquivos = base.exclude(caminho_documento="").count()
    pcfs = PCFTimeline.objects.count()
    pcfs_vinculadas = PCFTimeline.objects.exclude(documento_ged=None).count()
    transmittals = TransmittalKM.objects.count()
    transmittals_vinculados = TransmittalKM.objects.exclude(documento_ged=None).count()
    dox_total = DocumentoReferenciaExterna.objects.filter(sistema="DOX").count()
    dox_conformes = DocumentoReferenciaExterna.objects.filter(sistema="DOX", divergente=False).count()

    dimensoes = [
        {"chave": "vinculo_ged", "label": "Vínculo LD ↔ GED", "valor": _pct(vinculados, total), "lacunas": total - vinculados},
        {"chave": "responsavel", "label": "Responsável definido", "valor": _pct(responsaveis, total), "lacunas": total - responsaveis},
        {"chave": "cronograma", "label": "Cronograma informado", "valor": _pct(cronograma, total), "lacunas": total - cronograma},
        {"chave": "arquivo", "label": "Caminho oficial cadastrado", "valor": _pct(arquivos, total), "lacunas": total - arquivos},
        {"chave": "pcf", "label": "PCF vinculada ao GED", "valor": _pct(pcfs_vinculadas, pcfs), "lacunas": pcfs - pcfs_vinculadas},
        {"chave": "transmittal", "label": "Transmittal vinculado ao GED", "valor": _pct(transmittals_vinculados, transmittals), "lacunas": transmittals - transmittals_vinculados},
        {"chave": "dox", "label": "Referência DOX conforme", "valor": _pct(dox_conformes, dox_total), "lacunas": dox_total - dox_conformes},
    ]
    pesos = {"vinculo_ged": 25, "responsavel": 15, "cronograma": 15, "arquivo": 10, "pcf": 15, "transmittal": 10, "dox": 10}
    score = round(sum(item["valor"] * pesos[item["chave"]] for item in dimensoes) / 100, 1)
    nivel = "CONFIÁVEL" if score >= 90 else "ATENÇÃO" if score >= 75 else "FRÁGIL"
    ultima_automacao = ExecucaoAutomacao.objects.filter(sucesso=True).aggregate(data=Max("finalizado_em"))["data"]
    return {
        "score": score,
        "nivel": nivel,
        "dimensoes": dimensoes,
        "ultima_automacao": ultima_automacao,
        "idade_horas": round((timezone.now() - ultima_automacao).total_seconds() / 3600, 1) if ultima_automacao else None,
    }


def capturar_snapshot_executivo(origem):
    registros = DocumentoLD.objects.filter(origem_aba=origem)
    inteligencia = montar_inteligencia_executiva(registros)
    qualidade = qualidade_dados_executiva(registros)
    campos = {
        "total": inteligencia["total"],
        "emitidos": inteligencia["emitidos"],
        "vencidos_nao_emitidos": inteligencia["vencidos_nao_emitidos"],
        "vencendo_30_dias": inteligencia["vencendo_30_dias"],
        "pcf_criticas": inteligencia["pcf_criticas"],
        "pcf_aguardando_resposta": inteligencia["pcf_aguardando_resposta"],
        "comentarios_abertos": inteligencia["comentarios_abertos"],
        "aprovados_sem_ressalvas": inteligencia["aprovados_sem_ressalvas"],
        "aderencia_prazo": inteligencia["aderencia_prazo"],
        "progresso": inteligencia["progresso"],
        "qualidade_dados": qualidade["score"],
        "metricas": {
            "recebidos_pendentes": inteligencia["recebidos_pendentes"],
            "nao_recebidos": inteligencia["nao_recebidos"],
            "emitidos_no_prazo": inteligencia["emitidos_no_prazo"],
            "emitidos_atrasados": inteligencia["emitidos_atrasados"],
            "total_riscos": inteligencia["total_riscos"],
        },
    }
    snapshot, _ = ExecutiveMetricSnapshot.objects.update_or_create(
        origem=origem,
        data_referencia=timezone.localdate(),
        defaults=campos,
    )
    return snapshot


def tendencia_executiva(origens):
    origem_lista = [origem for origem in origens if origem]
    serie = list(
        ExecutiveMetricSnapshot.objects.filter(origem__in=origem_lista)
        .order_by("data_referencia")
    )
    atual = serie[-1] if serie else None
    anterior = next((item for item in reversed(serie[:-1]) if item.data_referencia < atual.data_referencia), None) if atual else None
    return {
        "serie": serie[-12:],
        "atual": atual,
        "anterior": anterior,
        "delta_progresso": round(atual.progresso - anterior.progresso, 1) if atual and anterior else None,
        "delta_vencidos": atual.vencidos_nao_emitidos - anterior.vencidos_nao_emitidos if atual and anterior else None,
        "historico_suficiente": bool(atual and anterior),
    }
