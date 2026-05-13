from pathlib import Path

from django.conf import settings


LD_RAIZ_HISTORICA = Path(
    r"\\virm-rgr022\FILESERVER\Projetos\05_HANDYMAX\09. Doc Control"
)


def _texto(valor):
    return str(valor or "").strip()


def caminhos_candidatos_ld(caminho_salvo):
    """
    Gera caminhos candidatos para arquivos e pastas da LD.

    Mantém compatibilidade com:
    - caminhos absolutos
    - caminhos relativos salvos com ../
    - raiz configurada em settings.LD_BASE_PATH
    - raiz histórica do FILESERVER
    - bases locais de desenvolvimento
    """
    bruto = _texto(caminho_salvo).split("#", 1)[0].replace("/", "\\")
    candidatos = []

    if not bruto:
        return candidatos

    caminho_bruto = Path(bruto)
    candidatos.append(caminho_bruto)

    partes = [p for p in bruto.split("\\") if p and p not in {".", ".."}]
    relativo_sem_subida = Path(*partes) if partes else None

    bases = []

    base_path = _texto(getattr(settings, "LD_BASE_PATH", ""))
    if base_path:
        bases.append(Path(base_path))

    bases.append(LD_RAIZ_HISTORICA)

    base_dir = Path(getattr(settings, "BASE_DIR", Path.cwd()))
    bases.extend(
        [
            base_dir,
            base_dir.parent,
            Path.cwd(),
            Path.cwd().parent,
            Path.home(),
            Path.home() / "Documents",
            Path.home() / "OneDrive",
            Path.home() / "Desktop",
        ]
    )

    if relativo_sem_subida:
        for base in bases:
            candidatos.append(base / relativo_sem_subida)

    for base in bases:
        candidatos.append(base / caminho_bruto)

    unicos = []
    vistos = set()

    for candidato in candidatos:
        texto = str(candidato)
        if texto not in vistos:
            vistos.add(texto)
            unicos.append(candidato)

    return unicos


def resolver_caminho_ld(caminho_salvo):
    candidatos = caminhos_candidatos_ld(caminho_salvo)

    for candidato in candidatos:
        if candidato.exists():
            return candidato, candidatos

    return None, candidatos


def gerar_hyperlink_ld(caminho_salvo):
    arquivo, _ = resolver_caminho_ld(caminho_salvo)
    if arquivo:
        return arquivo.resolve().as_uri()

    return _texto(caminho_salvo)
