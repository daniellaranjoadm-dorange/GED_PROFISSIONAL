from pathlib import Path

service_path = Path("apps/automacoes/services/kongsberg_document_list.py")

if not service_path.exists():
    raise SystemExit(f"Arquivo não encontrado: {service_path}")

text = service_path.read_text(encoding="utf-8")

start = text.find("def _compactar_documento(")
end = text.find("\ndef _model_has_field", start)

if start == -1 or end == -1:
    raise SystemExit("Não encontrei o bloco _compactar_documento para substituir.")

new_block = """
def _texto_limpo(valor: Any) -> str:
    texto = _texto(valor).upper()
    texto = texto.replace("\\\\", "/").split("/")[-1]
    texto = texto.replace("_", "-")
    texto = " ".join(texto.split())
    return texto.strip()


def _compactar_documento(valor: Any) -> str:
    return "".join(ch for ch in _texto_limpo(valor) if ch.isalnum())


def _tokens_documento(valor: Any) -> list[str]:
    texto = _texto_limpo(valor)
    return [t for t in re.split(r"[^A-Z0-9]+", texto) if t]


def _remover_revisao_compacta(valor: str) -> str:
    texto = str(valor or "").upper()
    texto = re.sub(r"(REV|REVISAO|REVISÃO|R)[A-Z0-9]{1,3}$", "", texto)
    texto = re.sub(r"[A-Z]$", "", texto) if len(texto) > 10 else texto
    return texto


def _score_documental(km_valor: Any, ld_valor: Any) -> int:
    km = _compactar_documento(km_valor)
    ld = _compactar_documento(ld_valor)

    if not km or not ld:
        return 0

    if km == ld:
        return 100

    km_sem_rev = _remover_revisao_compacta(km)
    ld_sem_rev = _remover_revisao_compacta(ld)

    if km_sem_rev and ld_sem_rev and km_sem_rev == ld_sem_rev:
        return 96

    if len(km_sem_rev) >= 8 and km_sem_rev in ld_sem_rev:
        return 88

    if len(ld_sem_rev) >= 8 and ld_sem_rev in km_sem_rev:
        return 84

    km_tokens = _tokens_documento(km_valor)
    ld_texto = _texto_limpo(ld_valor)
    ld_compacto = _compactar_documento(ld_valor)

    tokens_relevantes = [t for t in km_tokens if len(t) >= 2]

    if tokens_relevantes:
        hits_texto = sum(1 for t in tokens_relevantes if t in ld_texto)
        hits_compacto = sum(1 for t in tokens_relevantes if t in ld_compacto)
        cobertura = max(hits_texto, hits_compacto) / max(len(tokens_relevantes), 1)

        if cobertura >= 1:
            return 76

        if cobertura >= 0.75 and len(tokens_relevantes) >= 4:
            return 68

    km_numeros = re.findall(r"\\d+", _texto_limpo(km_valor))
    ld_numeros = re.findall(r"\\d+", _texto_limpo(ld_valor))

    if km_numeros and ld_numeros:
        comuns = set(km_numeros).intersection(ld_numeros)
        if len(comuns) >= 3:
            return 64
        if len(comuns) >= 2 and any(len(n) >= 3 for n in comuns):
            return 58

    return 0

"""

text = text[:start] + new_block + text[end:]

start = text.find("def _buscar_ld_para_km(")
end = text.find("\ndef executar_cruzamento_ld_km", start)

if start == -1 or end == -1:
    raise SystemExit("Não encontrei o bloco _buscar_ld_para_km para substituir.")

new_buscar_ld = """
def _buscar_ld_para_km(numero_km: str):
    campos = [
        "numero_documento_km",
        "documento",
        "titulo",
        "caminho_documento",
        "caminho_grd",
        "caminho_pcf",
        "caminho_resposta",
        "caminho_grd_resposta",
    ]

    numero_km_txt = _texto(numero_km)
    numero_km_compacto = _compactar_documento(numero_km)

    if not numero_km_compacto:
        return None, 0

    query = Q()

    for campo in campos:
        if not _model_has_field(DocumentoLD, campo):
            continue

        query |= Q(**{f"{campo}__icontains": numero_km_txt})

        for token in _tokens_documento(numero_km_txt):
            if len(token) >= 4:
                query |= Q(**{f"{campo}__icontains": token})

    candidatos = list(DocumentoLD.objects.filter(query).distinct().order_by("-id")[:1200]) if query else []

    if not candidatos:
        candidatos = list(DocumentoLD.objects.exclude(documento="").order_by("-id")[:3000])

    melhor = None
    melhor_score = 0

    for item in candidatos:
        for campo in campos:
            if not _model_has_field(DocumentoLD, campo):
                continue

            valor = getattr(item, campo, "")
            score = _score_documental(numero_km_txt, valor)

            if campo == "numero_documento_km":
                score += 8 if score else 0
            elif campo == "documento":
                score += 5 if score else 0

            if score > melhor_score:
                melhor = item
                melhor_score = min(score, 100)

            if melhor_score >= 96:
                return melhor, melhor_score

    return melhor, melhor_score

"""

text = text[:start] + new_buscar_ld + text[end:]

service_path.write_text(text, encoding="utf-8")

print("OK: motor de match KM ↔ LD melhorado.")
print("Agora rode:")
print("python manage.py check")
print("python manage.py test apps.automacoes apps.contas")
print("Depois clique em Executar Sync KM ↔ LD novamente.")
