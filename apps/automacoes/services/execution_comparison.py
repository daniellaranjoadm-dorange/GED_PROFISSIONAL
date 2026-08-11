from apps.automacoes.models import DocumentoKM, DocumentoLD, KMFileIndex, PCFTimeline, TransmittalKM


def capturar_snapshot_operacional():
    """Captura indicadores pequenos e estáveis para comparação de execuções."""
    try:
        return {
            "ld_total": DocumentoLD.objects.count(),
            "ld_com_pcf": DocumentoLD.objects.exclude(pcf="").count(),
            "ld_vinculada_km": DocumentoLD.objects.exclude(numero_documento_km="").count(),
            "pcf_total": PCFTimeline.objects.count(),
            "pcf_com_comentarios": PCFTimeline.objects.filter(open_comments__gt=0).count(),
            "km_total": DocumentoKM.objects.count(),
            "km_recebidos": DocumentoKM.objects.filter(
                status_recebimento=DocumentoKM.STATUS_RECEBIMENTO_RECEBIDO
            ).count(),
            "km_vinculados_ld": DocumentoKM.objects.exclude(documento_ld=None).count(),
            "transmittals_total": TransmittalKM.objects.count(),
            "indice_km_ativo": KMFileIndex.objects.filter(ativo=True).count(),
        }
    except Exception:
        return {}


def comparar_snapshots(antes, depois):
    antes = antes or {}
    depois = depois or {}
    chaves = sorted(set(antes) | set(depois))
    delta = {
        chave: int(depois.get(chave, 0) or 0) - int(antes.get(chave, 0) or 0)
        for chave in chaves
    }
    labels = {
        "ld_total": "Documentos LD",
        "ld_com_pcf": "LDs com PCF",
        "ld_vinculada_km": "LDs vinculadas ao KM",
        "pcf_total": "PCFs indexadas",
        "pcf_com_comentarios": "PCFs com comentários abertos",
        "km_total": "Documentos KM",
        "km_recebidos": "Documentos KM recebidos",
        "km_vinculados_ld": "Documentos KM vinculados à LD",
        "transmittals_total": "Transmittals KM",
        "indice_km_ativo": "Arquivos ativos no índice KM",
    }
    return {
        "antes": antes,
        "depois": depois,
        "delta": delta,
        "linhas": [
            {
                "chave": chave,
                "label": labels.get(chave, chave),
                "antes": int(antes.get(chave, 0) or 0),
                "depois": int(depois.get(chave, 0) or 0),
                "delta": delta[chave],
            }
            for chave in chaves
        ],
        "alteracoes": sum(1 for valor in delta.values() if valor != 0),
    }


def extrair_arquivos_publicados(resultado):
    """Extrai referências de saída devolvidas pelas rotinas sem presumir um formato único."""
    if not isinstance(resultado, dict):
        return []

    encontrados = []
    marcadores = ("arquivo", "caminho", "saida", "output", "dashboard", "html", "xlsx", "pptx", "pdf")
    for chave, valor in resultado.items():
        if not any(marcador in str(chave).lower() for marcador in marcadores):
            continue
        valores = valor if isinstance(valor, (list, tuple, set)) else [valor]
        for item in valores:
            if isinstance(item, str) and item.strip() and item.strip() not in encontrados:
                encontrados.append(item.strip())
    return encontrados[:30]
