import re
from datetime import date, datetime, timedelta

from django.conf import settings


SLA_DIAS_UTEIS = 15
ALERTA_DIAS_UTEIS = 3
ESCOPO_PROJETO = "LD Projeto Basico"


def _date_value(value):
    if isinstance(value, datetime):
        return value.date()
    if isinstance(value, date):
        return value
    text = str(value or "").strip()
    for fmt in ("%d/%m/%Y", "%d/%m/%y", "%Y-%m-%d", "%Y-%m-%d %H:%M:%S"):
        try:
            return datetime.strptime(text, fmt).date()
        except ValueError:
            continue
    return None


def _int_value(value):
    match = re.search(r"-?\d+", str(value or ""))
    return int(match.group()) if match else 0


def _revision_from_pcf(value):
    match = re.search(r"_R([0-9A-Z]+)", str(value or "").upper())
    return match.group(1) if match else ""


def document_type(value):
    """Extrai a sigla documental de códigos como I-DE-..., I-PT-... e PR-...."""
    parts = [part for part in str(value or "").upper().strip().split("-") if part]
    if not parts:
        return "OUTROS"
    candidate = parts[1] if len(parts) > 1 and len(parts[0]) == 1 else parts[0]
    return candidate if candidate.isalpha() and 2 <= len(candidate) <= 4 else "OUTROS"


def _alpha_number(value):
    total = 0
    for char in value:
        if not char.isalpha():
            return 0
        total = total * 26 + ord(char) - ord("A") + 1
    return total


def _number_alpha(value):
    result = ""
    while value > 0:
        value, remainder = divmod(value - 1, 26)
        result = chr(ord("A") + remainder) + result
    return result


def resposta_esperada(revisao_pcf, revisao_documento):
    received = str(revisao_pcf or "").upper().strip()
    base = str(revisao_documento or "").upper().strip()
    if not received or not base or not received.startswith(base):
        return ""
    suffix = received[len(base):]
    next_number = 1 if not suffix else _alpha_number(suffix) + 1
    return f"{base}{_number_alpha(next_number)}" if next_number else ""


def _easter(year):
    a = year % 19
    b, c = divmod(year, 100)
    d, e = divmod(b, 4)
    f = (b + 8) // 25
    g = (b - f + 1) // 3
    h = (19 * a + b - d - g + 15) % 30
    i, k = divmod(c, 4)
    l = (32 + 2 * e + 2 * i - h - k) % 7
    m = (a + 11 * h + 22 * l) // 451
    month = (h + l - 7 * m + 114) // 31
    day = (h + l - 7 * m + 114) % 31 + 1
    return date(year, month, day)


def holidays(year):
    easter = _easter(year)
    values = {
        date(year, 1, 1), date(year, 4, 21), date(year, 5, 1),
        date(year, 9, 7), date(year, 10, 12), date(year, 11, 2),
        date(year, 11, 15), date(year, 11, 20), date(year, 12, 25),
        easter - timedelta(days=48), easter - timedelta(days=47),
        easter - timedelta(days=2), easter + timedelta(days=60),
    }
    for raw in getattr(settings, "PCF_FERIADOS", []):
        parsed = _date_value(raw)
        if parsed and parsed.year == year:
            values.add(parsed)
    return values


def is_business_day(day):
    return day.weekday() < 5 and day not in holidays(day.year)


def add_business_days(start, amount):
    current = start
    added = 0
    while added < amount:
        current += timedelta(days=1)
        if is_business_day(current):
            added += 1
    return current


def business_days_between(start, end):
    if not start or not end or end <= start:
        return 0
    current = start
    total = 0
    while current < end:
        current += timedelta(days=1)
        if is_business_day(current):
            total += 1
    return total


def build_record(document, today=None):
    today = today or date.today()
    received_date = _date_value(document.data_pcf)
    response_date = _date_value(document.data_resposta)
    received_revision = _revision_from_pcf(document.pcf)
    response_revision = _revision_from_pcf(document.pcf_resposta)
    expected_revision = resposta_esperada(received_revision, document.revisao)
    paired = bool(
        received_revision and response_revision
        and response_revision == expected_revision
        and (not received_date or not response_date or response_date >= received_date)
    )

    deadline = add_business_days(received_date, SLA_DIAS_UTEIS) if received_date else None
    reference_date = response_date if paired and response_date else today
    unanswered_days = business_days_between(received_date, reference_date) if received_date else None
    overdue_days = business_days_between(deadline, reference_date) if deadline and reference_date > deadline else 0
    remaining_days = business_days_between(today, deadline) if deadline and today <= deadline else 0

    if not paired:
        responsible = "McLaren"
    elif deadline and response_date and response_date > deadline:
        responsible = "Transpetro — resposta em atraso"
    else:
        responsible = "Transpetro"

    if paired:
        situation, color = "Respondida", "azul"
    elif not received_date:
        situation, color = "Sem informação", "cinza"
    elif today > deadline:
        situation, color = "Vencida", "vermelho"
    elif remaining_days <= ALERTA_DIAS_UTEIS:
        situation, color = "Aguardando resposta", "amarelo"
    else:
        situation, color = "Aguardando resposta", "verde"

    open_comments = _int_value(document.open_comments)
    under_review = _int_value(document.under_review)
    total_comments = _int_value(document.qtd_comentarios)
    closed_comments = total_comments - open_comments - under_review
    comments_consistent = closed_comments >= 0
    critical_score = overdue_days * 10 + open_comments * 3 + under_review * 2

    return {
        "id": document.pk,
        "projeto": ESCOPO_PROJETO,
        "disciplina": document.disciplina or "-",
        "documento": document.documento,
        "titulo": document.titulo or "-",
        "tipo_documento": document_type(document.documento),
        "revisao": document.revisao,
        "pcf": document.pcf,
        "data_recebimento": received_date,
        "resposta_esperada": f"R{expected_revision}" if expected_revision else "-",
        # AB/AC representam exclusivamente a resposta do ciclo atual de Y.
        # Respostas históricas não podem aparecer como se respondessem à PCF vigente.
        "pcf_resposta": document.pcf_resposta if paired else "",
        "data_resposta": response_date if paired else None,
        "resposta_ciclo_atual": paired,
        "situacao": situation,
        "cor": color,
        "dias_sem_resposta": unanswered_days,
        "prazo": deadline,
        "dias_atraso": overdue_days,
        "dias_restantes": remaining_days,
        "status": document.status_final_pcf or document.status or "-",
        "qtd_comentarios": total_comments,
        "open_comments": open_comments,
        "under_review": under_review,
        "closed_comments": closed_comments,
        "comments_consistent": comments_consistent,
        "responsavel": responsible,
        "grd": document.grd or "-",
        "caminho_pcf": document.caminho_pcf,
        "caminho_documento": document.caminho_documento,
        "criticidade": critical_score,
    }


def summarize(records):
    pending = [item for item in records if item["situacao"] == "Aguardando resposta"]
    overdue = [item for item in records if item["situacao"] == "Vencida"]
    answered = [item for item in records if item["situacao"] == "Respondida"]
    due_soon = [item for item in pending if item["cor"] == "amarelo"]
    response_times = [item["dias_sem_resposta"] for item in answered if item["dias_sem_resposta"] is not None]
    total_comments = sum(item["qtd_comentarios"] for item in records)
    open_comments = sum(item["open_comments"] for item in records)
    under_review = sum(item["under_review"] for item in records)
    closed_comments = sum(item["closed_comments"] for item in records)
    return {
        "total": len(records),
        "aguardando": len(pending),
        "vencidas": len(overdue),
        "vencendo": len(due_soon),
        "respondidas": len(answered),
        "tempo_medio": round(sum(response_times) / len(response_times), 1) if response_times else 0,
        "comentarios_total": total_comments,
        "comentarios_abertos": open_comments,
        "comentarios_revisao": under_review,
        "comentarios_fechados": closed_comments,
        "comentarios_reconciliacao": total_comments - open_comments - under_review - closed_comments,
        "comentarios_inconsistentes": sum(not item["comments_consistent"] for item in records),
        "exposicao_pct": round(len(overdue) / len(records) * 100, 1) if records else 0,
        "resposta_pct": round(len(answered) / len(records) * 100, 1) if records else 0,
    }


def executive_dashboard(records):
    total = len(records)
    situations = []
    situation_colors = {
        "Vencida": "#ef4444",
        "Aguardando resposta": "#f59e0b",
        "Respondida": "#38bdf8",
        "Sem informação": "#64748b",
        "Sem informaÃ§Ã£o": "#64748b",
    }
    for label in ("Vencida", "Aguardando resposta", "Respondida", "Sem informaÃ§Ã£o"):
        count = sum(1 for item in records if item["situacao"] == label)
        situations.append({
            "label": label,
            "total": count,
            "pct": round(count / total * 100, 1) if total else 0,
            "cor": situation_colors[label],
        })

    grouped = {}
    for item in records:
        bucket = grouped.setdefault(item["tipo_documento"], {"total": 0, "vencidas": 0, "open": 0})
        bucket["total"] += 1
        bucket["vencidas"] += int(item["situacao"] == "Vencida")
        bucket["open"] += item["open_comments"]
    max_total = max((item["total"] for item in grouped.values()), default=1)
    types = []
    for label, values in sorted(grouped.items(), key=lambda pair: (-pair[1]["total"], pair[0])):
        types.append({
            "label": label,
            **values,
            "pct": round(values["total"] / total * 100, 1) if total else 0,
            "bar_pct": round(values["total"] / max_total * 100, 1),
        })
    return {"situacoes": situations, "tipos": types}
