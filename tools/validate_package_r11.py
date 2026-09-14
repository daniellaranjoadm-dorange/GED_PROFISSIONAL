from pathlib import Path
from html.parser import HTMLParser
from pypdf import PdfReader
import zipfile, re

base=Path(r"D:\GED_PROFISSIONAL\outputs\pacote_diretoria_r11")
html=base/"DASHBOARD_GESTAO_INTEGRADA_DOC_CONTROL_R13.html"
xlsx=base/"HISTOGRAMA_INTEGRADO_DOC_CONTROL_ARQUIVO_TECNICO_R11.xlsx"
pptx=base/"APRESENTACAO_DIRETORIA_GESTAO_INTEGRADA_R11.pptx"
pdf=base/"RELATORIO_EXECUTIVO_GESTAO_INTEGRADA_R11.pdf"
for p in (html,xlsx,pptx,pdf): assert p.exists() and p.stat().st_size>1000, p
t=html.read_text(encoding="utf-8"); HTMLParser().feed(t)
assert t.count('class="view')==4 and t.count('class="tab')>=4
assert all(name in t for name in (xlsx.name,pptx.name,pdf.name))
assert "R$ 1,459" in t and "1.113,5" in t and "684,0" in t
assert len(PdfReader(str(pdf)).pages)==6
for p in (xlsx,pptx):
    with zipfile.ZipFile(p) as z: assert z.testzip() is None
print({p.name:p.stat().st_size for p in (html,xlsx,pptx,pdf)})
