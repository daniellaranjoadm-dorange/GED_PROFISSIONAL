from __future__ import annotations

import io
import re
import unicodedata
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path

import fitz
import numpy as np
from pypdf import PdfReader
from reportlab.lib.colors import HexColor, white
from reportlab.lib.units import mm
from reportlab.pdfgen import canvas


COR_VERMELHA = HexColor("#C00000")
ALTURA_CARIMBO = 35 * mm
LARGURA_CARIMBO = 70 * mm
ALTURA_CARIMBO_COMPACTO = 9 * mm
LARGURA_CARIMBO_COMPACTO = 90 * mm
MARGEM_FAIXA = 7 * mm
ALTURA_FAIXA = ALTURA_CARIMBO + (2 * MARGEM_FAIXA)


class PdfStampError(Exception):
    """Erro seguro para apresentação ao usuário."""


@dataclass(frozen=True)
class CopiaControladaGerada:
    conteudo: bytes
    nome_arquivo: str
    total_paginas: int


def _texto_limpo(valor: str) -> str:
    return " ".join(str(valor).split()).strip()


def _nome_seguro(valor: str, limite: int = 80) -> str:
    normalizado = unicodedata.normalize("NFKD", valor)
    ascii_texto = normalizado.encode("ascii", "ignore").decode("ascii")
    seguro = re.sub(r"[^A-Za-z0-9._-]+", "_", ascii_texto).strip("._-")
    return (seguro or "DOCUMENTO")[:limite]


def _tem_assinatura_digital(reader: PdfReader) -> bool:
    try:
        campos = reader.get_fields() or {}
    except Exception:
        return False
    return any(str(campo.get("/FT", "")) == "/Sig" for campo in campos.values())


def _criar_faixa(
    largura: float,
    altura_total: float,
    *,
    numero_gi: str,
    usuario: str,
    emitido_em: datetime,
    emitido_por: str = "",
    pagina: int,
    total_paginas: int,
    posicao_carimbo: tuple[float, float] | None = None,
    modo_compacto: bool = False,
) -> bytes:
    memoria = io.BytesIO()
    pdf = canvas.Canvas(memoria, pagesize=(largura, altura_total))
    pdf.setTitle("Cópia Controlada")

    largura_carimbo = LARGURA_CARIMBO_COMPACTO if modo_compacto else LARGURA_CARIMBO
    altura_carimbo = ALTURA_CARIMBO_COMPACTO if modo_compacto else ALTURA_CARIMBO
    x, y = posicao_carimbo or (
        largura - MARGEM_FAIXA - largura_carimbo,
        MARGEM_FAIXA,
    )
    cabecalho = 8.5 * mm

    # Fundo branco translúcido reduz a interferência do desenho sem criar uma
    # tarja totalmente opaca sobre a informação técnica.
    pdf.saveState()
    if hasattr(pdf, "setFillAlpha"):
        pdf.setFillAlpha(0.90)
    pdf.setFillColor(white)
    pdf.rect(x, y, largura_carimbo, altura_carimbo, stroke=0, fill=1)
    pdf.restoreState()

    if modo_compacto:
        pdf.setStrokeColor(COR_VERMELHA)
        pdf.setLineWidth(1)
        pdf.rect(x, y, largura_carimbo, altura_carimbo, stroke=1, fill=0)
        pdf.setFillColor(COR_VERMELHA)
        pdf.setFont("Helvetica-Bold", 7)
        pdf.drawString(x + 3 * mm, y + altura_carimbo - 3.4 * mm, "CÓPIA CONTROLADA MARENOVA")
        pdf.setFont("Helvetica", 5.5)
        pdf.drawString(x + 3 * mm, y + 2.2 * mm, f"DESTINATÁRIO: {usuario[:34]}  |  GUIA: {numero_gi[:36]}")
        pdf.save()
        return memoria.getvalue()

    pdf.setStrokeColor(COR_VERMELHA)
    pdf.setLineWidth(1.25)
    pdf.rect(x, y, LARGURA_CARIMBO, ALTURA_CARIMBO, stroke=1, fill=0)
    pdf.setFillColor(COR_VERMELHA)
    pdf.rect(
        x,
        y + ALTURA_CARIMBO - cabecalho,
        LARGURA_CARIMBO,
        cabecalho,
        stroke=0,
        fill=1,
    )
    pdf.setFillColor(white)
    pdf.setFont("Helvetica-Bold", 10)
    pdf.drawCentredString(
        x + (LARGURA_CARIMBO / 2),
        y + ALTURA_CARIMBO - 5.7 * mm,
        "CÓPIA CONTROLADA MARENOVA",
    )

    pdf.setFillColor(COR_VERMELHA)
    pdf.setFont("Helvetica-Bold", 7)
    pdf.drawCentredString(
        x + (LARGURA_CARIMBO / 2),
        y + ALTURA_CARIMBO - 11.7 * mm,
        "IMPRESSÃO CONTROLADA PELO GED",
    )

    linhas = (
        ("GI", numero_gi),
        ("DESTINATÁRIO", usuario),
        ("EMITIDO POR", emitido_por or usuario),
        ("EMISSÃO", emitido_em.strftime("%d/%m/%Y %H:%M")),
    )
    pos_y = y + ALTURA_CARIMBO - 16.2 * mm
    for rotulo, valor in linhas:
        pdf.setFont("Helvetica-Bold", 5.7)
        pdf.drawString(x + 3 * mm, pos_y, f"{rotulo}:")
        pdf.setFont("Helvetica", 6.2)
        pdf.drawString(x + 22 * mm, pos_y, valor[:48])
        pos_y -= 4.25 * mm

    pdf.save()
    return memoria.getvalue()


def _posicao_com_menos_conteudo(pagina: fitz.Page) -> tuple[float, float, bool]:
    largura = float(pagina.rect.width)
    altura = float(pagina.rect.height)
    margem = float(MARGEM_FAIXA)
    carimbo_l = float(LARGURA_CARIMBO)
    carimbo_a = float(ALTURA_CARIMBO)
    escala = 0.22
    pix = pagina.get_pixmap(matrix=fitz.Matrix(escala, escala), colorspace=fitz.csGRAY, alpha=False)
    tons = np.frombuffer(pix.samples, dtype=np.uint8).reshape(pix.height, pix.width)
    escuros = (tons < 242).astype(np.int32)
    integral = np.pad(escuros, ((1, 0), (1, 0))).cumsum(axis=0).cumsum(axis=1)

    def pontuacao(x: float, y: float, w: float, h: float) -> float:
        x1 = max(0, min(pix.width - 1, int(x * escala)))
        y1 = max(0, min(pix.height - 1, int(y * escala)))
        x2 = max(x1 + 1, min(pix.width, int((x + w) * escala)))
        y2 = max(y1 + 1, min(pix.height, int((y + h) * escala)))
        total = integral[y2, x2] - integral[y1, x2] - integral[y2, x1] + integral[y1, x1]
        return float(total) / ((x2 - x1) * (y2 - y1))

    passo = 14.0
    candidatos = []
    y = margem
    while y <= altura - margem - carimbo_a:
        x = margem
        while x <= largura - margem - carimbo_l:
            candidatos.append((pontuacao(x, y, carimbo_l, carimbo_a), x, y))
            x += passo
        y += passo
    melhor_score, x, y_topo = min(candidatos, key=lambda item: item[0])
    # Só utiliza o carimbo completo quando a janela está efetivamente vazia.
    if melhor_score <= 0.0001:
        return x, altura - y_topo - carimbo_a, False

    compacto_l = float(LARGURA_CARIMBO_COMPACTO)
    compacto_a = float(ALTURA_CARIMBO_COMPACTO)
    compactos = []
    for y_topo in (margem, altura - margem - compacto_a):
        x = margem
        while x <= largura - margem - compacto_l:
            compactos.append((pontuacao(x, y_topo, compacto_l, compacto_a), x, y_topo))
            x += passo
    _, x, y_topo = min(compactos, key=lambda item: item[0])
    return x, altura - y_topo - compacto_a, True


def _criar_folha_controle(
    *,
    numero_gi: str,
    usuario: str,
    emitido_por: str,
    emitido_em: datetime,
    nome_original: str,
    total_paginas: int,
) -> bytes:
    memoria = io.BytesIO()
    largura, altura = 297 * mm, 210 * mm
    pdf = canvas.Canvas(memoria, pagesize=(largura, altura))
    pdf.setTitle("Folha de Controle - Cópia Controlada Marenova")
    pdf.setFillColor(HexColor("#C00000"))
    pdf.rect(0, altura - 28 * mm, largura, 28 * mm, stroke=0, fill=1)
    pdf.setFillColor(white)
    pdf.setFont("Helvetica-Bold", 22)
    pdf.drawString(18 * mm, altura - 18 * mm, "CÓPIA CONTROLADA MARENOVA")
    pdf.setFillColor(HexColor("#111827"))
    pdf.setFont("Helvetica-Bold", 14)
    pdf.drawString(18 * mm, altura - 48 * mm, "FOLHA DE CONTROLE DA DISTRIBUIÇÃO")
    dados = (
        ("GUIA DE EMISSÃO", numero_gi),
        ("DESTINATÁRIO", usuario),
        ("EMITIDO POR", emitido_por or usuario),
        ("DATA DE EMISSÃO", emitido_em.strftime("%d/%m/%Y %H:%M")),
        ("DOCUMENTO DE ORIGEM", nome_original),
        ("FOLHAS TÉCNICAS", str(total_paginas)),
    )
    y = altura - 66 * mm
    for rotulo, valor in dados:
        pdf.setFillColor(HexColor("#6B7280"))
        pdf.setFont("Helvetica-Bold", 8)
        pdf.drawString(18 * mm, y, rotulo)
        pdf.setFillColor(HexColor("#111827"))
        pdf.setFont("Helvetica", 12)
        pdf.drawString(67 * mm, y, str(valor)[:90])
        pdf.setStrokeColor(HexColor("#D1D5DB"))
        pdf.line(18 * mm, y - 3 * mm, largura - 18 * mm, y - 3 * mm)
        y -= 16 * mm
    pdf.setFillColor(HexColor("#F3F4F6"))
    pdf.roundRect(18 * mm, 22 * mm, largura - 36 * mm, 34 * mm, 4 * mm, stroke=0, fill=1)
    pdf.setFillColor(HexColor("#374151"))
    pdf.setFont("Helvetica-Bold", 11)
    pdf.drawString(25 * mm, 44 * mm, "INTEGRIDADE DAS INFORMAÇÕES TÉCNICAS")
    pdf.setFont("Helvetica", 10)
    pdf.drawString(25 * mm, 34 * mm, "As folhas seguintes foram preservadas sem carimbos, tarjas ou sobreposições sobre o desenho.")
    pdf.drawString(25 * mm, 27 * mm, "Esta folha identifica e controla a cópia distribuída ao destinatário indicado acima.")
    pdf.save()
    return memoria.getvalue()


def gerar_copia_controlada(
    conteudo_pdf: bytes,
    *,
    nome_original: str,
    numero_gi: str,
    usuario: str,
    emitido_em: datetime,
    emitido_por: str = "",
    corrigir_orientacao_paisagem: bool = False,
    posicionar_em_espaco_livre: bool = False,
    usar_folha_controle: bool = False,
) -> CopiaControladaGerada:
    numero_gi = _texto_limpo(numero_gi)
    usuario = _texto_limpo(usuario)
    if not numero_gi or not usuario:
        raise PdfStampError("Informe o número da GI e o usuário da cópia.")

    try:
        reader = PdfReader(io.BytesIO(conteudo_pdf))
    except Exception as exc:
        raise PdfStampError("Não foi possível abrir o PDF selecionado.") from exc

    if reader.is_encrypted:
        raise PdfStampError(
            "O PDF possui proteção por senha. Remova a proteção antes de gerar a cópia."
        )
    if _tem_assinatura_digital(reader):
        raise PdfStampError(
            "O PDF possui assinatura digital. O carimbo invalidaria a assinatura; "
            "utilize uma versão não assinada."
        )
    if not reader.pages:
        raise PdfStampError("O PDF não possui páginas.")

    total_paginas = len(reader.pages)

    try:
        origem = fitz.open(stream=conteudo_pdf, filetype="pdf")
        destino = fitz.open()
        destino.insert_pdf(origem)
        for indice in range(total_paginas):
            pagina_saida = destino[indice]
            # Normaliza a rotação declarada no PDF sem alterar sua aparência.
            # Assim desenhos landscape continuam landscape após a faixa inferior.
            if pagina_saida.rotation:
                pagina_saida.remove_rotation()
            if corrigir_orientacao_paisagem and pagina_saida.rect.height > pagina_saida.rect.width:
                pagina_saida.set_rotation(270)
                pagina_saida.remove_rotation()
            largura = float(pagina_saida.rect.width)
            altura = float(pagina_saida.rect.height)
            if usar_folha_controle:
                posicao_carimbo = None
                modo_compacto = False
                continue
            if posicionar_em_espaco_livre:
                x_carimbo, y_carimbo, modo_compacto = _posicao_com_menos_conteudo(pagina_saida)
                posicao_carimbo = (x_carimbo, y_carimbo)
            else:
                posicao_carimbo = None
                modo_compacto = False
            # Preserva exatamente o tamanho original da folha. O carimbo é
            # sobreposto no canto inferior direito, sem criar bordas adicionais.
            faixa_bytes = _criar_faixa(
                largura,
                altura,
                numero_gi=numero_gi,
                usuario=usuario,
                emitido_por=emitido_por,
                emitido_em=emitido_em,
                pagina=indice + 1,
                total_paginas=total_paginas,
                posicao_carimbo=posicao_carimbo,
                modo_compacto=modo_compacto,
            )
            faixa = fitz.open(stream=faixa_bytes, filetype="pdf")
            pagina_saida.show_pdf_page(pagina_saida.rect, faixa, 0, overlay=True)
            faixa.close()
        if usar_folha_controle:
            folha_bytes = _criar_folha_controle(
                numero_gi=numero_gi,
                usuario=usuario,
                emitido_por=emitido_por,
                emitido_em=emitido_em,
                nome_original=nome_original,
                total_paginas=total_paginas,
            )
            folha = fitz.open(stream=folha_bytes, filetype="pdf")
            destino.insert_pdf(folha, start_at=0)
            folha.close()
        destino.set_metadata(
            {
                "title": "Cópia Controlada",
                "subject": f"GI/GE {numero_gi} - Usuário {usuario}",
                "creator": "GED Profissional",
            }
        )
        # Os documentos de engenharia já chegam comprimidos; recomprimir dezenas
        # de páginas adiciona quase um minuto sem redução material do arquivo.
        conteudo_saida = destino.tobytes(garbage=1, deflate=False)
        destino.close()
        origem.close()
    except Exception as exc:
        raise PdfStampError(
            "Não foi possível aplicar o carimbo a todas as páginas do PDF."
        ) from exc

    nome_base = _nome_seguro(Path(nome_original).stem)
    gi_segura = _nome_seguro(numero_gi, limite=40)
    pessoa_segura = _nome_seguro(usuario, limite=60)
    return CopiaControladaGerada(
        conteudo=conteudo_saida,
        nome_arquivo=f"{nome_base}_{gi_segura}_{pessoa_segura}.pdf",
        total_paginas=total_paginas,
    )
