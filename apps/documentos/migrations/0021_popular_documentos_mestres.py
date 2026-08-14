import re
import unicodedata

from django.db import migrations


def normalizar(valor):
    texto = unicodedata.normalize("NFKD", str(valor or ""))
    texto = "".join(c for c in texto if not unicodedata.combining(c))
    return re.sub(r"[^A-Z0-9]", "", texto.upper())


def peso_revisao(valor):
    texto = str(valor or "0").strip().upper()
    if texto.isdigit():
        return (0, int(texto))
    return (1, texto)


def popular_mestres(apps, schema_editor):
    Documento = apps.get_model("documentos", "Documento")
    DocumentoMestre = apps.get_model("documentos", "DocumentoMestre")
    grupos = {}
    for documento in Documento.objects.all().order_by("id"):
        chave = normalizar(documento.codigo)
        if not chave:
            continue
        mestre, _ = DocumentoMestre.objects.get_or_create(
            codigo_normalizado=chave,
            defaults={
                "codigo": documento.codigo,
                "titulo": documento.titulo or "",
                "disciplina": documento.disciplina or "",
            },
        )
        Documento.objects.filter(pk=documento.pk).update(mestre_id=mestre.pk)
        grupos.setdefault(mestre.pk, []).append(documento)

    for mestre_id, revisoes in grupos.items():
        atuais = [item for item in revisoes if item.ativo and item.deletado_em is None]
        candidatas = atuais or revisoes
        atual = max(candidatas, key=lambda item: (peso_revisao(item.revisao), item.id))
        DocumentoMestre.objects.filter(pk=mestre_id).update(revisao_atual_id=atual.pk)


class Migration(migrations.Migration):
    dependencies = [("documentos", "0020_documentoreferenciaexterna_conferido_em_and_more")]
    operations = [migrations.RunPython(popular_mestres, migrations.RunPython.noop)]
