from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path

from django.utils import timezone
from pypdf import PdfReader


class GuiaParseError(Exception):
    pass


@dataclass(frozen=True)
class DestinatarioGuia:
    nome: str
    email: str = ""
    na_guia: bool = True


@dataclass(frozen=True)
class DocumentoGuia:
    numero: str
    folha: str
    revisao: str


@dataclass(frozen=True)
class DadosGuia:
    numero: str
    data_emissao: datetime
    remetente: str
    email_remetente: str
    destinatarios: tuple[DestinatarioGuia, ...]
    documentos: tuple[DocumentoGuia, ...]
    caminho: Path
    pasta_documentos: Path


EMAIL_RE = r"[\w.+-]+@[\w.-]+\.[A-Za-z]{2,}"
DESTINATARIOS_COMPLEMENTARES = (
    "Transpetro",
    "Planejamento",
    "SMS",
    "SGI",
    "Desmantelamento",
    "Produção",
)


def _normalizar_nome_destinatario(nome: str) -> str:
    nome = " ".join(nome.split())
    return {
        "planejamneto": "Planejamento",
        "contrutibilidade": "Construtibilidade",
    }.get(nome.casefold(), nome)


def normalizar_documento(valor: str) -> str:
    return re.sub(r"[^A-Z0-9]", "", valor.upper())


def _texto_layout(caminho: Path) -> str:
    try:
        reader = PdfReader(str(caminho))
        return "\n".join(
            pagina.extract_text(extraction_mode="layout") or ""
            for pagina in reader.pages
        )
    except Exception as exc:
        raise GuiaParseError("Não foi possível ler o PDF da guia.") from exc


def _primeiro(padrao: str, texto: str, descricao: str) -> re.Match:
    match = re.search(padrao, texto, flags=re.IGNORECASE | re.MULTILINE)
    if not match:
        raise GuiaParseError(f"Não foi possível identificar {descricao} na guia.")
    return match


def ler_guia(caminho: Path, pasta_documentos: Path | None = None) -> DadosGuia:
    texto = _texto_layout(caminho)
    guia_match = _primeiro(
        r"(ECXP\d{5}[/-]\d{2}-\d{2}-(?:GI|GE)-\d{4,5}[/-]\d{2})",
        texto,
        "o número da GI/GE",
    )
    data_match = _primeiro(
        r"Data:\s*(\d{2}/\d{2}/\d{4}\s+\d{2}:\d{2})",
        texto,
        "a data de emissão",
    )
    remetente_match = _primeiro(
        rf"Remetente:\s*(.*?)\s*-\s*\(({EMAIL_RE})\)",
        texto,
        "o remetente",
    )

    data_emissao = datetime.strptime(data_match.group(1), "%d/%m/%Y %H:%M")
    if timezone.is_naive(data_emissao):
        data_emissao = timezone.make_aware(data_emissao)

    destinatarios = []
    principal = re.search(
        rf"A/C:\s*(.*?)\s*-\s*Fone:.*?\(({EMAIL_RE})\)",
        texto,
        flags=re.IGNORECASE,
    )
    if principal:
        destinatarios.append(
            DestinatarioGuia(_normalizar_nome_destinatario(principal.group(1)), principal.group(2).strip())
        )

    for match in re.finditer(
        rf"(?mi)^\s*([^\r\n]{{3,80}}?)\s{{2,}}({EMAIL_RE})\s*$",
        texto,
    ):
        nome = _normalizar_nome_destinatario(match.group(1))
        email = match.group(2).strip()
        if nome.upper() not in {"REMETENTE", "EMISSOR"}:
            destinatarios.append(DestinatarioGuia(nome, email))

    unicos = {}
    for destinatario in destinatarios:
        unicos[destinatario.nome.casefold()] = destinatario
    if not unicos:
        raise GuiaParseError("Não foi possível identificar os recebedores da guia.")
    for nome in DESTINATARIOS_COMPLEMENTARES:
        unicos.setdefault(nome.casefold(), DestinatarioGuia(nome, "", na_guia=False))

    documentos = []
    for match in re.finditer(
        r"(?m)^\s*(\d{4,6}-[A-Z0-9/-]+(?:\.\d+)?)\s+(\S+)\s+([A-Z0-9]+)\s+",
        texto,
    ):
        documentos.append(
            DocumentoGuia(
                numero=match.group(1).strip(),
                folha=match.group(2).strip(),
                revisao=match.group(3).strip(),
            )
        )
    if not documentos:
        raise GuiaParseError("Não foi possível identificar os documentos e revisões.")

    return DadosGuia(
        numero=caminho.stem,
        data_emissao=data_emissao,
        remetente=" ".join(remetente_match.group(1).split()),
        email_remetente=remetente_match.group(2).strip(),
        destinatarios=tuple(unicos.values()),
        documentos=tuple(documentos),
        caminho=caminho,
        pasta_documentos=pasta_documentos or caminho.with_suffix(""),
    )
