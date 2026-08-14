import re
import unicodedata

from django.db import transaction

from apps.automacoes.models import DocumentoLD
from apps.documentos.models import Documento, LogAuditoria


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


@transaction.atomic
def cadastrar_documentos_ausentes_da_ld(*, usuario=None) -> dict[str, int]:
    """Cria uma identidade GED por código/revisão ausente e vincula suas LDs."""
    pendentes = list(
        DocumentoLD.objects.select_for_update()
        .filter(documento_ged__isnull=True)
        .order_by("id")
    )
    grupos = {}
    for registro in pendentes:
        chave = (
            normalizar_identificador(registro.documento),
            normalizar_revisao(registro.revisao),
        )
        if chave[0]:
            grupos.setdefault(chave, []).append(registro)

    indice_existentes = {}
    for documento in Documento.objects.filter(ativo=True, deletado_em__isnull=True).only(
        "id", "codigo", "revisao"
    ):
        chave = (
            normalizar_identificador(documento.codigo),
            normalizar_revisao(documento.revisao),
        )
        indice_existentes.setdefault(chave, []).append(documento.id)

    resultado = {
        "linhas": len(pendentes), "criados": 0, "vinculados": 0,
        "existentes_reutilizados": 0, "ambiguos": 0,
    }
    for chave, registros in grupos.items():
        principal = registros[0]
        existentes = indice_existentes.get(chave, [])
        if len(existentes) == 1:
            DocumentoLD.objects.filter(pk__in=[item.pk for item in registros]).update(
                documento_ged_id=existentes[0]
            )
            resultado["vinculados"] += len(registros)
            resultado["existentes_reutilizados"] += 1
            continue
        if len(existentes) > 1:
            resultado["ambiguos"] += 1
            continue
        documento = Documento.objects.create(
            codigo=str(principal.documento or "").strip(),
            revisao=str(principal.revisao or "0").strip() or "0",
            titulo=str(principal.titulo or principal.documento or "Sem título").strip(),
            disciplina=str(principal.disciplina or "").strip() or None,
            status_documento=str(principal.status_documento or "").strip() or None,
            status_emissao=str(principal.status_grd or "").strip() or None,
        )
        DocumentoLD.objects.filter(pk__in=[item.pk for item in registros]).update(
            documento_ged=documento
        )
        LogAuditoria.objects.create(
            usuario=usuario,
            documento=documento,
            acao="Cadastro automático via LD",
            descricao=(
                f"Criado a partir de {principal.origem_aba}; "
                f"{len(registros)} registro(s) LD vinculado(s)."
            ),
        )
        resultado["criados"] += 1
        resultado["vinculados"] += len(registros)

    return resultado
