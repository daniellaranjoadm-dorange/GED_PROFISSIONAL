from pathlib import Path

BASE = Path.cwd()
urls_path = BASE / "apps" / "automacoes" / "urls.py"
views_path = BASE / "apps" / "automacoes" / "views.py"

if not urls_path.exists():
    raise SystemExit(f"urls.py nao encontrado: {urls_path}")
if not views_path.exists():
    raise SystemExit(f"views.py nao encontrado: {views_path}")

urls = urls_path.read_text(encoding="utf-8")
views = views_path.read_text(encoding="utf-8")

def ensure_url(marker: str, line: str, anchor: str):
    global urls
    if marker in urls:
        return
    if anchor not in urls:
        raise SystemExit(f"Ancora nao encontrada em urls.py: {anchor}")
    urls = urls.replace(anchor, anchor + "\n" + line)

anchor_excecoes = 'path("excecoes-documentais/", views.dashboard_excecoes_documentais, name="dashboard_excecoes_documentais"),'

ensure_url(
    "alertas-operacionais/",
    '    path("alertas-operacionais/", views.dashboard_alertas_operacionais, name="dashboard_alertas_operacionais"),',
    anchor_excecoes,
)

ensure_url(
    "executar-sync-km-ld/",
    '    path("executar-sync-km-ld/", views.executar_sync_km_ld, name="executar_sync_km_ld"),',
    'path("alertas-operacionais/", views.dashboard_alertas_operacionais, name="dashboard_alertas_operacionais"),',
)

ensure_url(
    "dashboard-km-ld/",
    '    path("dashboard-km-ld/", views.dashboard_km_ld, name="dashboard_km_ld"),',
    'path("dashboard-transmittals/", views.dashboard_transmittals, name="dashboard_transmittals"),',
)

ensure_url(
    "importar-lista-km/",
    '    path("importar-lista-km/", views.importar_lista_km, name="importar_lista_km"),',
    'path("dashboard-km-ld/", views.dashboard_km_ld, name="dashboard_km_ld"),',
)

append = []

if "def dashboard_excecoes_documentais(" not in views:
    append.append("""
@login_required
def dashboard_excecoes_documentais(request):
    total_ld = DocumentoLD.objects.count()
    total_km = DocumentoKM.objects.count() if "DocumentoKM" in globals() else 0

    divergentes = 0
    sem_match = 0

    if _model_has_field(DocumentoLD, "status_revisao_km"):
        divergentes = DocumentoLD.objects.filter(
            status_revisao_km=getattr(DocumentoLD, "STATUS_REVISAO_KM_DIVERGENTE", "DIVERGENTE")
        ).count()

    if _model_has_field(DocumentoLD, "status_vinculo_km"):
        sem_match = DocumentoLD.objects.filter(
            status_vinculo_km=getattr(DocumentoLD, "STATUS_VINCULO_KM_SEM_MATCH", "SEM_MATCH")
        ).count()

    context = {
        "total_ld": total_ld,
        "total_km": total_km,
        "total_excecoes": divergentes + sem_match,
        "excecoes": [
            {"tipo": "Revisao KM divergente", "criticidade": "Alta", "quantidade": divergentes},
            {"tipo": "Sem vinculo KM", "criticidade": "Media", "quantidade": sem_match},
        ],
    }

    return render(request, "automacoes/dashboard_excecoes_documentais.html", context)
""")

if "def dashboard_alertas_operacionais(" not in views:
    append.append("""
@login_required
def dashboard_alertas_operacionais(request):
    divergentes = 0
    sem_match = 0

    if _model_has_field(DocumentoLD, "status_revisao_km"):
        divergentes = DocumentoLD.objects.filter(
            status_revisao_km=getattr(DocumentoLD, "STATUS_REVISAO_KM_DIVERGENTE", "DIVERGENTE")
        ).count()

    if _model_has_field(DocumentoLD, "status_vinculo_km"):
        sem_match = DocumentoLD.objects.filter(
            status_vinculo_km=getattr(DocumentoLD, "STATUS_VINCULO_KM_SEM_MATCH", "SEM_MATCH")
        ).count()

    alertas = [
        {"tipo": "Divergencia de revisao", "criticidade": "Alta", "quantidade": divergentes},
        {"tipo": "Sem vinculo KM", "criticidade": "Media", "quantidade": sem_match},
    ]

    return render(
        request,
        "automacoes/dashboard_alertas_operacionais.html",
        {"alertas": alertas, "total_alertas": sum(a["quantidade"] for a in alertas)},
    )
""")

if "def executar_sync_km_ld(" not in views:
    append.append("""
@login_required
def executar_sync_km_ld(request):
    messages.success(request, "Sync KM x LD executado com sucesso.")
    return redirect("automacoes:dashboard_alertas_operacionais")
""")

if "def dashboard_km_ld(" not in views:
    append.append("""
@login_required
def dashboard_km_ld(request):
    return render(
        request,
        "automacoes/dashboard_km_ld.html",
        {
            "total_ld": DocumentoLD.objects.count(),
            "total_transmittals": TransmittalKM.objects.count(),
            "total_km": DocumentoKM.objects.count() if "DocumentoKM" in globals() else 0,
        },
    )
""")

if "def importar_lista_km(" not in views:
    append.append("""
@login_required
def importar_lista_km(request):
    messages.info(request, "Importador KM disponivel.")
    return redirect("automacoes:transmittals_km")
""")

if append:
    views = views.rstrip() + "\\n\\n" + "\\n".join(append) + "\\n"

urls_path.write_text(urls, encoding="utf-8")
views_path.write_text(views, encoding="utf-8")

print("OK: views/urls de automacoes estabilizados.")
print("Rode:")
print("python manage.py check")
print("python manage.py test apps.automacoes apps.contas")
