from pathlib import Path

service_path = Path("apps/automacoes/services/kongsberg_document_list.py")

if not service_path.exists():
    raise SystemExit(f"Arquivo não encontrado: {service_path}")

text = service_path.read_text(encoding="utf-8")

if "import re" not in text:
    lines = text.splitlines()
    insert_at = 0

    for i, line in enumerate(lines):
        if line.startswith("from __future__"):
            insert_at = i + 1
            break

    lines.insert(insert_at, "import re")
    text = "\n".join(lines) + "\n"
    service_path.write_text(text, encoding="utf-8")

print("OK: import re garantido em kongsberg_document_list.py")
print("Agora rode:")
print("python manage.py check")
print("python manage.py test apps.automacoes apps.contas")
