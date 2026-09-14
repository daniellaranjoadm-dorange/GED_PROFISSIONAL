"""Monta um candidato íntegro usando layout v3 e dados da publicação mais recente."""

from __future__ import annotations

import re
import sys
from pathlib import Path


def _bloco(texto: str, padrao: str, nome: str) -> str:
    match = re.search(padrao, texto, flags=re.DOTALL)
    if not match:
        raise ValueError(f"Bloco {nome} não encontrado.")
    return match.group(1)


def construir(layout_path: Path, dados_path: Path, output_path: Path) -> None:
    if output_path.exists():
        raise FileExistsError(f"O candidato já existe: {output_path}")

    layout = layout_path.read_text(encoding="utf-8")
    recente = dados_path.read_text(encoding="utf-8")

    dados = _bloco(recente, r"const DATA=(.*?),META=", "DATA")
    meta = _bloco(recente, r",META=(.*?);const FILES=", "META")
    arquivos = _bloco(recente, r"const FILES=(.*?);(?:const |function |\n)", "FILES")

    pacote = f"const DATA={dados},META={meta};const FILES={arquivos};\n"
    candidato, total = re.subn(
        r"const DATA=.*?,META=.*?;const FILES=.*?;(?:const |function |\n)",
        lambda _match: pacote,
        layout,
        count=1,
        flags=re.DOTALL,
    )
    if total != 1:
        raise ValueError("Não foi possível substituir o pacote de dados no layout v3.")

    output_path.write_text(candidato, encoding="utf-8")
    print(f"CANDIDATO={output_path}")
    print(f"BYTES={output_path.stat().st_size}")
    print(f"REGISTROS={dados.count(chr(34) + 'documento' + chr(34) + ':')}")


if __name__ == "__main__":
    if len(sys.argv) != 4:
        raise SystemExit("Uso: repair_dashboard_candidate.py LAYOUT_V3 DADOS_ATUAIS SAIDA")
    construir(*(Path(value) for value in sys.argv[1:]))
