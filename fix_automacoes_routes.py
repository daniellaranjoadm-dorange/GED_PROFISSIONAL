from pathlib import Path

BASE = Path.cwd()
urls_path = BASE / "apps" / "automacoes" / "urls.py"
views_path = BASE / "apps" / "automacoes" / "views.py"

urls = urls_path.read_text(encoding="utf-8")
views = views_path.read_text(encoding="utf-8")

anchor = 'path("excecoes-documentais/", views.dashboard_excecoes_documentais, name="dashboard_excecoes_documentais"),'

routes_to_add = [
    (
        "dashboard-km-ld/",
        '    path("dashboard-km-ld/", views.dashboard_km_ld, name="dashboard_km_ld"),'
    ),
    (
        "importar-lista-km/",
        '    path("importar-lista-km/", views.importar_lista_km, name="importar_lista_km"),'
    ),
    (
        "alertas-operacionais/",
        '    path("alertas-operacionais/", views.dashboard_alertas_operacionais, name="dashboard_alertas_operacionais"),'
    ),
]

if anchor not in urls:
    raise SystemExit("Ancora de URL nao encontrada. Nao alterei nada.")

for marker, route in routes_to_add:
    if marker not in urls:
        urls = urls.replace(anchor, anchor + "\n" + route)

views_to_append = []

if "def dashboard_km_ld(" not in views:
    views_to_append.append("""
@login_required
def dashboard_km_ld(request):
    context = {
        "total_ld": DocumentoLD.objects.count(),
        "total_transmittals": TransmittalKM.objects.count(),
        "total_km": DocumentoKM.objects.count() if "DocumentoKM" in globals() else 0,
    }

    return render(
        request,
        "automacoes/dashboard_km_ld.html",
        context,
    )
""")

if "def importar_lista_km(" not in views:
    views_to_append.append("""
@login_required
def importar_lista_km(request):
    messages.info(request, "Importador KM disponivel.")
    return redirect("automacoes:transmittals_km")
""")

if "def dashboard_alertas_operacionais(" not in views:
    views_to_append.append("""
@login_required
def dashboard_alertas_operacionais(request):
    alertas = [
        {
            "tipo": "Divergencia de revisao",
            "criticidade": "Alta",
            "quantidade": DocumentoLD.objects.filter(
                status_revisao_km=DocumentoLD.STATUS_REVISAO_KM_DIVERGENTE
            ).count(),
        },
        {
            "tipo": "Sem vinculo KM",
            "criticidade": "Media",
            "quantidade": DocumentoLD.objects.filter(
                status_vinculo_km=DocumentoLD.STATUS_VINCULO_KM_SEM_MATCH
            ).count(),
        },
    ]

    context = {
        "alertas": alertas,
        "total_alertas": sum(a["quantidade"] for a in alertas),
    }

    return render(
        request,
        "automacoes/dashboard_alertas_operacionais.html",
        context,
    )
""")

if views_to_append:
    views = views.rstrip() + "\n\n" + "\n".join(views_to_append) + "\n"

urls_path.write_text(urls, encoding="utf-8")
views_path.write_text(views, encoding="utf-8")

print("OK: apps/automacoes/urls.py e views.py corrigidos.")
print("Agora rode:")
print("python manage.py check")
print("python manage.py test apps.automacoes apps.contas")
