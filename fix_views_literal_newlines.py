from pathlib import Path
import py_compile
import sys

views_path = Path("apps/automacoes/views.py")

if not views_path.exists():
    raise SystemExit(f"Arquivo nao encontrado: {views_path}")

text = views_path.read_text(encoding="utf-8")

# Corrige artefatos literais gerados por patch anterior:
# exemplo invalido: )\n\n
replacements = {
    ")\\n\\n": ")\n\n",
    ")\\n": ")\n",
    "\\n\\n@login_required": "\n\n@login_required",
    "\\n@login_required": "\n@login_required",
    "\\n\\ndef ": "\n\ndef ",
    "\\ndef ": "\ndef ",
}

for old, new in replacements.items():
    text = text.replace(old, new)

# Remove sequencias literais perdidas em linhas isoladas.
lines = []
for line in text.splitlines():
    stripped = line.strip()
    if stripped in {r"\n", r"\n\n"}:
        continue
    lines.append(line)

text = "\n".join(lines).rstrip() + "\n"
views_path.write_text(text, encoding="utf-8")

try:
    py_compile.compile(str(views_path), doraise=True)
except Exception as exc:
    print("ERRO: views.py ainda nao compila.")
    print(exc)
    sys.exit(1)

print("OK: views.py limpo e compilando.")
print("Agora rode:")
print("python manage.py check")
print("python manage.py test apps.automacoes apps.contas")
