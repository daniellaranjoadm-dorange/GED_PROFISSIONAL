import pymupdf as fitz
from pathlib import Path
from django.conf import settings
from PIL import ImageChops, Image, ImageDraw

def gerar_diff_pdf(pdf1_path, pdf2_path, output_name):
    """
    Compara dois PDFs página a página e gera outro PDF com as diferenças.
    """

    pdf1 = fitz.open(pdf1_path)
    pdf2 = fitz.open(pdf2_path)

    # Pasta onde o diff final será salvo
    output_dir = Path(settings.MEDIA_ROOT) / "diffs"
    output_dir.mkdir(parents=True, exist_ok=True)

    output_file = output_dir / f"{output_name}.pdf"

    diff_doc = fitz.open()  # novo PDF de saída

    total_paginas = max(len(pdf1), len(pdf2))

    for page_number in range(total_paginas):

        # Pega páginas (ou cria em branco se não existir)
        page1 = pdf1[page_number] if page_number < len(pdf1) else None
        page2 = pdf2[page_number] if page_number < len(pdf2) else None

        # Converte em imagem raster
        pix1 = page1.get_pixmap(dpi=150) if page1 else None
        pix2 = page2.get_pixmap(dpi=150) if page2 else None

        # Converte para PIL
        img1 = Image.frombytes("RGB", [pix1.width, pix1.height], pix1.samples) if pix1 else None
        img2 = Image.frombytes("RGB", [pix2.width, pix2.height], pix2.samples) if pix2 else None

        # Se uma página não existir, cria imagem branca
        if img1 is None:
            img1 = Image.new("RGB", img2.size, (255, 255, 255))
        if img2 is None:
            img2 = Image.new("RGB", img1.size, (255, 255, 255))

        # Calcula diferenças
        diff = ImageChops.difference(img1, img2)

        # Cria camada de destaque
        draw = ImageDraw.Draw(diff)
        bbox = diff.getbbox()

        if bbox:
            draw.rectangle(bbox, outline="red", width=5)

        # Salva página como PNG temporariamente
        tmp_png = output_dir / f"_tmp_page_{page_number}.png"
        diff.save(tmp_png)

        # Adiciona ao PDF final
        diff_page = diff_doc.new_page(width=diff.width, height=diff.height)
        diff_page.insert_image(diff_page.rect, filename=str(tmp_png))

        tmp_png.unlink()  # apaga PNG temporário

    diff_doc.save(output_file)
    diff_doc.close()

    return str(output_file)
