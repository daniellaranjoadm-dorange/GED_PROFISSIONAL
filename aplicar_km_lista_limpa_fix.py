from pathlib import Path
import shutil
from datetime import datetime

ROOT = Path.cwd()
STAMP = datetime.now().strftime("%Y%m%d_%H%M%S")

def backup(path: Path) -> None:
    if path.exists():
        bak = path.with_suffix(path.suffix + f".bak_km_lista_limpa_{STAMP}")
        shutil.copy2(path, bak)
        print(f"[OK] backup criado: {bak}")

def remover_rotas_quebradas_urls() -> None:
    path = ROOT / "apps" / "automacoes" / "urls.py"
    if not path.exists():
        print(f"[AVISO] urls.py não encontrado: {path}")
        return

    backup(path)
    text = path.read_text(encoding="utf-8")

    linhas = text.splitlines()
    novas = []
    pulando = False
    buffer = []

    alvos = {
        "exportar_lista_km_excel",
        "exportar_lista_km_ppt",
    }

    for linha in linhas:
        if not pulando and "path(" in linha and any(alvo in linha for alvo in alvos):
            # rota em uma linha só
            if ")," in linha or linha.strip().endswith("),"):
                continue
            pulando = True
            buffer = [linha]
            continue

        if not pulando:
            novas.append(linha)
            continue

        buffer.append(linha)
        if ")," in linha or linha.strip().endswith("),"):
            pulando = False
            buffer = []

    if pulando:
        novas.extend(buffer)

    novo = "\n".join(novas).rstrip() + "\n"
    if novo != text:
        path.write_text(novo, encoding="utf-8")
        print("[OK] rotas quebradas lista-km/exportar-* removidas de urls.py")
    else:
        print("[OK] nenhuma rota quebrada encontrada em urls.py")

def atualizar_template_lista_km() -> None:
    origem = Path(__file__).resolve().parent / "apps" / "automacoes" / "templates" / "automacoes" / "lista_km.html"
    destino = ROOT / "apps" / "automacoes" / "templates" / "automacoes" / "lista_km.html"

    if not origem.exists():
        raise RuntimeError(f"Template de origem não encontrado no pacote: {origem}")

    if not destino.exists():
        raise RuntimeError(f"Template de destino não encontrado no projeto: {destino}")

    backup(destino)
    shutil.copy2(origem, destino)
    print("[OK] lista_km.html atualizado sem Score/Semântica/Vínculo LD")

def main():
    remover_rotas_quebradas_urls()
    atualizar_template_lista_km()
    print("\nPróximos comandos:")
    print("python manage.py check")
    print("python manage.py test apps.automacoes apps.contas")

if __name__ == "__main__":
    main()
