from collections import defaultdict
from datetime import date, datetime, timedelta
import unicodedata


FORMATOS_DATA = ("%d/%m/%Y", "%Y-%m-%d", "%d-%m-%Y")


def _texto(valor):
    return str(valor or "").strip()


def _normalizar(valor):
    texto = unicodedata.normalize("NFKD", _texto(valor))
    return "".join(c for c in texto if not unicodedata.combining(c)).casefold()


def _data(valor):
    texto = _texto(valor).split(" ")[0]
    for formato in FORMATOS_DATA:
        try:
            return datetime.strptime(texto, formato).date()
        except ValueError:
            continue
    return None


def _numero(valor):
    try:
        return int(float(_texto(valor).replace(",", ".")))
    except (TypeError, ValueError):
        return 0


def montar_inteligencia_executiva(registros, hoje=None):
    hoje = hoje or date.today()
    itens = list(registros)
    limite_30 = hoje + timedelta(days=30)

    total = len(itens)
    emitidos = 0
    aprovados_sem_ressalvas = 0
    recebidos_pendentes = 0
    nao_recebidos = 0
    pcf_criticas = 0
    pcf_aguardando_resposta = 0
    comentarios_abertos = 0
    planejados_ate_hoje = 0
    emitidos_no_prazo = 0
    emitidos_atrasados = 0
    vencidos_nao_emitidos = 0
    vencendo_30_dias = 0
    medicao_emissao = 0
    medicao_aprovacao = 0
    sem_responsavel = 0
    atraso_1_15 = 0
    atraso_16_30 = 0
    atraso_mais_30 = 0
    riscos = []
    risco_disciplina = defaultdict(int)

    for item in itens:
        status_doc = _normalizar(item.status_documento)
        status_grd = _normalizar(item.status_grd)
        status_pcf = _texto(item.status_final_pcf).upper()
        emitido = status_grd == "emitido"
        cancelado = "cancel" in status_doc
        prazo = _data(item.cronograma_termino)
        data_emissao = _data(item.data_grd)
        razoes = []
        dias_atraso = 0

        emitidos += int(emitido)
        aprovados_sem_ressalvas += int(status_doc == "aprovado sem comentarios")
        recebidos_pendentes += int(status_doc.startswith("recebido") and not emitido)
        nao_recebidos += int(status_doc == "nao recebido")
        pcf_criticas += int(status_pcf == "NOT RELEASED")
        requer_resposta = status_pcf in {"NOT RELEASED", "RELEASED WITH COMMENTS"}
        sem_resposta = not _texto(item.pcf_resposta)
        pcf_aguardando_resposta += int(requer_resposta and sem_resposta)
        comentarios_abertos += _numero(item.open_comments)
        sem_responsavel += int(not _texto(item.resp_for_issue))

        if prazo and not cancelado and prazo <= hoje:
            planejados_ate_hoje += 1
            if emitido and data_emissao and data_emissao <= prazo:
                emitidos_no_prazo += 1
            elif emitido:
                emitidos_atrasados += 1
            else:
                vencidos_nao_emitidos += 1
                dias_atraso = (hoje - prazo).days
                atraso_1_15 += int(dias_atraso <= 15)
                atraso_16_30 += int(15 < dias_atraso <= 30)
                atraso_mais_30 += int(dias_atraso > 30)
                razoes.append(f"Emissão vencida em {prazo:%d/%m/%Y}")
        elif prazo and not cancelado and not emitido and hoje < prazo <= limite_30:
            vencendo_30_dias += 1
            razoes.append(f"Emissão prevista até {prazo:%d/%m/%Y}")

        if status_pcf == "NOT RELEASED":
            razoes.append("PCF não liberada")
        if requer_resposta and sem_resposta:
            razoes.append("Resposta à PCF não registrada")
        if status_doc.startswith("recebido") and not emitido:
            razoes.append("Recebido e ainda não emitido")

        if _data(item.medicao_emissao):
            medicao_emissao += 1
        if _data(item.medicao_aprovacao):
            medicao_aprovacao += 1

        if razoes:
            severidade = 3 if (prazo and prazo < hoje and not emitido) or status_pcf == "NOT RELEASED" else 2
            if dias_atraso > 30 or (status_pcf == "NOT RELEASED" and requer_resposta and sem_resposta):
                severidade = 4
            disciplina = _texto(item.disciplina) or "Sem disciplina"
            risco_disciplina[disciplina] += 1
            if dias_atraso:
                impacto = "Risco ao marco de emissao"
                acao = "Confirmar recuperacao e nova data de emissao"
            elif status_pcf == "NOT RELEASED":
                impacto = "Bloqueio de liberacao tecnica"
                acao = "Tratar comentarios e responder a PCF"
            elif requer_resposta and sem_resposta:
                impacto = "Ciclo de aprovacao interrompido"
                acao = "Registrar resposta e evidencia de envio"
            else:
                impacto = "Pressao sobre o plano de curto prazo"
                acao = "Validar prontidao antes do vencimento"
            riscos.append({
                "item": item,
                "severidade": severidade,
                "razoes": razoes,
                "responsavel": _texto(item.resp_for_issue) or "Não definido",
                "prazo": prazo,
                "dias_atraso": dias_atraso,
                "impacto": impacto,
                "acao": acao,
            })

    riscos.sort(key=lambda x: (-x["severidade"], x["prazo"] or date.max, x["item"].documento))
    disciplinas_criticas = [
        {"label": disciplina, "total": quantidade}
        for disciplina, quantidade in sorted(risco_disciplina.items(), key=lambda x: (-x[1], x[0]))[:8]
    ]
    maior = max([x["total"] for x in disciplinas_criticas] or [1])
    for item in disciplinas_criticas:
        item["pct"] = round(item["total"] / maior * 100, 1)

    progresso = round(emitidos / total * 100, 1) if total else 0
    aderencia = round(emitidos_no_prazo / planejados_ate_hoje * 100, 1) if planejados_ate_hoje else 0
    liberacao = round(aprovados_sem_ressalvas / emitidos * 100, 1) if emitidos else 0
    nivel = "CRÍTICO" if vencidos_nao_emitidos or pcf_criticas >= 20 else "ATENÇÃO" if riscos else "CONTROLADO"

    return {
        "total": total,
        "emitidos": emitidos,
        "progresso": progresso,
        "aprovados_sem_ressalvas": aprovados_sem_ressalvas,
        "taxa_liberacao": liberacao,
        "recebidos_pendentes": recebidos_pendentes,
        "nao_recebidos": nao_recebidos,
        "pcf_criticas": pcf_criticas,
        "pcf_aguardando_resposta": pcf_aguardando_resposta,
        "comentarios_abertos": comentarios_abertos,
        "planejados_ate_hoje": planejados_ate_hoje,
        "emitidos_no_prazo": emitidos_no_prazo,
        "emitidos_atrasados": emitidos_atrasados,
        "vencidos_nao_emitidos": vencidos_nao_emitidos,
        "vencendo_30_dias": vencendo_30_dias,
        "aderencia_prazo": aderencia,
        "medicao_emissao": medicao_emissao,
        "medicao_aprovacao": medicao_aprovacao,
        "sem_responsavel": sem_responsavel,
        "atraso_1_15": atraso_1_15,
        "atraso_16_30": atraso_16_30,
        "atraso_mais_30": atraso_mais_30,
        "nivel": nivel,
        "riscos": riscos[:15],
        "riscos_todos": riscos,
        "total_riscos": len(riscos),
        "disciplinas_criticas": disciplinas_criticas,
        "atualizado_em": max((item.atualizado_em for item in itens), default=None),
    }
