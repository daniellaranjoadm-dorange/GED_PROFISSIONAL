"""Amplia a busca do dashboard LD para todos os valores do registro."""

from __future__ import annotations

import sys
from pathlib import Path


OLD_V2 = "[r.documento,r.titulo,r.grd,r.pcf,r.documentoKm,r.transmittalKm].some(v=>String(v||'').toLocaleLowerCase('pt-BR').includes(q))"
OLD_LEGACY = "[r.documento,r.titulo,r.grd,r.pcf,r.documentoKm].some(v=>String(v||'').toLocaleLowerCase('pt-BR').includes(q))"
ALL_VALUES = "Object.values(r).some(v=>(Array.isArray(v)?v:[v]).some(item=>String(item??'').toLocaleLowerCase('pt-BR').includes(q)))"


def update(path: Path) -> None:
    text = path.read_text(encoding="utf-8")
    original = text
    text = text.replace(OLD_V2, ALL_VALUES)
    text = text.replace(OLD_LEGACY, ALL_VALUES)
    text = text.replace(
        'placeholder="Buscar documento, título, GRD, PCF ou KM..."',
        'placeholder="Buscar em todas as colunas..."',
    )
    text = text.replace(
        'placeholder="Documento, título, GRD, PCF ou KM"',
        'placeholder="Buscar em todas as colunas..."',
    )

    if ALL_VALUES not in text:
        raise RuntimeError(f"Rotina de busca ampliada não encontrada: {path}")
    if text != original:
        temporary = path.with_suffix(path.suffix + ".tmp")
        temporary.write_text(text, encoding="utf-8")
        temporary.replace(path)
    print(f"OK|{path}|{path.stat().st_size}")


if __name__ == "__main__":
    for argument in sys.argv[1:]:
        update(Path(argument))
