import re
from pathlib import Path


SOURCE = Path(
    r"C:\Users\daniel.laranjo\.codex\visualizations\2026\08\03\019fc763-53de-7740-999c-b52eea40f680"
    r"\outputs\pcf_html_dashboard\dashboard_pcf_diretoria.html"
)
TARGET = Path(r"D:\GED_PROFISSIONAL\apps\automacoes\templates\automacoes\pcf_dashboard_bi.html")

html = SOURCE.read_text(encoding="utf-8")
html, count = re.subn(
    r"let DATA=.*?;\nconst \$=",
    "let DATA={{ pcf_dashboard_data|safe }};\nconst $=",
    html,
    count=1,
    flags=re.DOTALL,
)
if count != 1:
    raise RuntimeError("Não foi possível localizar o bloco de dados do dashboard.")
html = html.replace(">Base incorporada</span>", ">{{ pcf_source_label }}</span>", 1)
TARGET.write_text(html, encoding="utf-8")
print(TARGET)
