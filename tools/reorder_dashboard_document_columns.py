"""Reordena as colunas DOX/Transpetro do dashboard LD sem alterar os dados."""

from __future__ import annotations

import sys
from pathlib import Path


OLD_HEADER = (
    "<th>Documento</th><th>Rev.</th><th>Título</th><th>Disciplina</th>"
    "<th>Status</th><th>Emissão</th><th>Prazo</th><th>GRD</th><th>PCF</th>"
    "<th>Status PCF</th><th>OPEN</th><th>Responsável</th><th>KM</th>"
)
NEW_HEADER = (
    "<th>Nº DOCUMENTO DOX</th><th>Nº TRANSPETRO</th><th>Rev.</th><th>Título</th>"
    "<th>Disciplina</th><th>Status</th><th>Emissão</th><th>Prazo</th><th>GRD</th>"
    "<th>PCF</th><th>Status PCF</th><th>OPEN</th><th>Responsável</th><th>KM</th>"
)

OLD_ROW = (
    "'<tr><td><strong>'+esc(r.documento)+'</strong></td><td>'+esc(r.revisao)+'</td>"
    "<td>'+esc(r.titulo)+'</td><td>'+esc(r.disciplina)+'</td><td>'+badge(r.status)+'</td>"
    "<td>'+badge(r.statusEmissao)+'</td><td>'+badge(deadline(r))+'</td>"
    "<td>'+esc(r.grd||'-')+'</td><td>'+esc(r.pcf||'-')+'</td><td>'+badge(r.statusPcf)+'</td>"
    "<td>'+fmt(r.open)+'</td><td>'+esc(r.responsavel)+'</td><td>'+esc(r.documentoKm||'-')+'</td></tr>'"
)
NEW_ROW = (
    "'<tr><td><strong>'+esc(r.ldExport?.[1]||'-')+'</strong></td>"
    "<td><strong>'+esc(r.documento)+'</strong></td><td>'+esc(r.revisao)+'</td>"
    "<td>'+esc(r.titulo)+'</td><td>'+esc(r.disciplina)+'</td>"
    "<td>'+badge(r.status)+'</td><td>'+badge(r.statusEmissao)+'</td>"
    "<td>'+badge(deadline(r))+'</td><td>'+esc(r.grd||'-')+'</td>"
    "<td>'+esc(r.pcf||'-')+'</td><td>'+badge(r.statusPcf)+'</td><td>'+fmt(r.open)+'</td>"
    "<td>'+esc(r.responsavel)+'</td><td>'+esc(r.documentoKm||'-')+'</td></tr>'"
)


def update(path: Path) -> None:
    text = path.read_text(encoding="utf-8")
    original = text

    if OLD_HEADER in text:
        text = text.replace(OLD_HEADER, NEW_HEADER, 1)
    elif NEW_HEADER not in text:
        raise RuntimeError(f"Cabeçalho esperado não encontrado: {path}")

    if OLD_ROW in text:
        text = text.replace(OLD_ROW, NEW_ROW, 1)
    elif NEW_ROW not in text:
        raise RuntimeError(f"Renderização esperada não encontrada: {path}")

    # O link DOX fica na nova primeira coluna; a PCF avança uma posição.
    old_dox_link = "if(cells[0])cells[0].innerHTML='<strong>'+linked(r.documento,r.linkDox"
    new_dox_link = "if(cells[0])cells[0].innerHTML='<strong>'+linked(r.ldExport?.[1]||'-',r.linkDox"
    if old_dox_link in text:
        text = text.replace(old_dox_link, new_dox_link, 1)
    elif new_dox_link not in text:
        raise RuntimeError(f"Ajuste do link DOX não encontrado: {path}")

    old_pcf_link = "if(cells[8])cells[8].innerHTML=linked(r.pcf||'-',r.linkPcf"
    new_pcf_link = "if(cells[9])cells[9].innerHTML=linked(r.pcf||'-',r.linkPcf"
    if old_pcf_link in text:
        text = text.replace(old_pcf_link, new_pcf_link, 1)
    elif new_pcf_link not in text:
        raise RuntimeError(f"Ajuste do link PCF não encontrado: {path}")

    if text != original:
        temporary = path.with_suffix(path.suffix + ".tmp")
        temporary.write_text(text, encoding="utf-8")
        temporary.replace(path)
    print(f"OK|{path}|{path.stat().st_size}")


if __name__ == "__main__":
    for argument in sys.argv[1:]:
        update(Path(argument))
