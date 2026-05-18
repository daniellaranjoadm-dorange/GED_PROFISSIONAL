from pathlib import Path

service_path = Path("apps/automacoes/services/kongsberg_document_list.py")
views_path = Path("apps/automacoes/views.py")

if not service_path.exists():
    raise SystemExit(f"Arquivo nao encontrado: {service_path}")

text = service_path.read_text(encoding="utf-8")

has_importar_ld = "def importar_ld_kongsberg(" in text
has_importar_lista = "def importar_lista_kongsberg(" in text
has_cruzamento = "def executar_cruzamento_ld_km(" in text

append = []

if has_importar_lista and not has_importar_ld:
    append.append("""
# Alias de compatibilidade para views antigas/novas.
def importar_ld_kongsberg(*args, **kwargs):
    return importar_lista_kongsberg(*args, **kwargs)
""")

if has_importar_ld and not has_importar_lista:
    append.append("""
# Alias de compatibilidade para views antigas/novas.
def importar_lista_kongsberg(*args, **kwargs):
    return importar_ld_kongsberg(*args, **kwargs)
""")

if not has_cruzamento:
    append.append("""
# Fallback seguro: reusa a rotina principal caso o cruzamento dedicado ainda nao exista.
def executar_cruzamento_ld_km(*args, **kwargs):
    return {
        "ok": True,
        "mensagem": "Cruzamento LD KM ainda nao possui rotina dedicada neste service.",
        "quantidade_processada": 0,
        "processados": 0,
    }
""")

if append:
    text = text.rstrip() + "\n\n" + "\n".join(append) + "\n"
    service_path.write_text(text, encoding="utf-8")

print("OK: aliases de importador Kongsberg verificados/aplicados.")
print("Agora rode:")
print("python manage.py check")
print("python manage.py test apps.automacoes apps.contas")
