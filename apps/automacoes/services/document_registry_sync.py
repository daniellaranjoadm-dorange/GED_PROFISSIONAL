import re
import unicodedata

from apps.automacoes.models import DocumentoLD
from apps.documentos.models import Documento


def normalizar_identificador(valor: str) -> str:
    texto = unicodedata.normalize("NFKD", str(valor or ""))
    texto = "".join(char for char in texto if not unicodedata.combining(char))
    return re.sub(r"[^A-Z0-9]", "", texto.upper())


def normalizar_revisao(valor: str) -> str:
    texto = str(valor or "").strip().upper()
    texto = re.sub(r"^(REV(?:ISAO)?[.\s_-]*)", "", texto)
    return texto.lstrip("0") or "0"


def sincronizar_documentos_ld_com_ged() -> dict[str, int]:
    """Vincula LD ao cadastro central sem criar documentos ou adivinhar ambiguidades."""
    indice: dict[tuple[str, str], list[int]] = {}
    for item in Documento.objects.filter(ativo=True, deletado_em__isnull=True).only(
        "id", "codigo", "revisao"
    ):
        chave = (normalizar_identificador(item.codigo), normalizar_revisao(item.revisao))
        indice.setdefault(chave, []).append(item.id)

    resultado = {"processados": 0, "vinculados": 0, "sem_match": 0, "ambiguos": 0}
    for registro in DocumentoLD.objects.only("id", "documento", "revisao", "documento_ged_id"):
        resultado["processados"] += 1
        chave = (
            normalizar_identificador(registro.documento),
            normalizar_revisao(registro.revisao),
        )
        candidatos = indice.get(chave, [])
        if len(candidatos) == 1:
            documento_id = candidatos[0]
            if registro.documento_ged_id != documento_id:
                DocumentoLD.objects.filter(pk=registro.pk).update(documento_ged_id=documento_id)
            resultado["vinculados"] += 1
        elif len(candidatos) > 1:
            resultado["ambiguos"] += 1
        else:
            resultado["sem_match"] += 1
    return resultado
