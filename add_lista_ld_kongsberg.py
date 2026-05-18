from pathlib import Path
import py_compile

BASE = Path.cwd()
views_path = BASE / "apps" / "automacoes" / "views.py"
urls_path = BASE / "apps" / "automacoes" / "urls.py"
base_path = BASE / "templates" / "documentos" / "base.html"
template_dir = BASE / "apps" / "automacoes" / "templates" / "automacoes"
template_path = template_dir / "lista_km.html"

for path in [views_path, urls_path]:
    if not path.exists():
        raise SystemExit(f"Arquivo não encontrado: {path}")

views = views_path.read_text(encoding="utf-8")
urls = urls_path.read_text(encoding="utf-8")

if "from apps.automacoes.models import" in views:
    import_line = views.split("from apps.automacoes.models import", 1)[1].split("\n", 1)[0]
    if "DocumentoKM" not in import_line:
        views = views.replace("DocumentoLD,", "DocumentoLD, DocumentoKM,")

if "def listar_km(" not in views:
    view_code = '''
@login_required
def listar_km(request):
    busca = request.GET.get("q", "").strip()
    status = request.GET.get("status", "").strip()
    disciplina = request.GET.get("disciplina", "").strip()

    registros = DocumentoKM.objects.all().order_by("numero_km")

    if busca:
        registros = registros.filter(
            Q(numero_km__icontains=busca)
            | Q(titulo__icontains=busca)
            | Q(disciplina__icontains=busca)
            | Q(status_km__icontains=busca)
            | Q(transmittal_numero__icontains=busca)
            | Q(documento_tp__icontains=busca)
        )

    if status and _model_has_field(DocumentoKM, "status_km"):
        registros = registros.filter(status_km__icontains=status)

    if disciplina and _model_has_field(DocumentoKM, "disciplina"):
        registros = registros.filter(disciplina__icontains=disciplina)

    total = registros.count()

    total_recebidos = (
        DocumentoKM.objects.filter(
            status_recebimento=getattr(DocumentoKM, "STATUS_RECEBIMENTO_RECEBIDO", "RECEBIDO")
        ).count()
        if _model_has_field(DocumentoKM, "status_recebimento")
        else 0
    )

    total_pendentes = (
        DocumentoKM.objects.filter(
            status_recebimento=getattr(DocumentoKM, "STATUS_RECEBIMENTO_PENDENTE", "PENDENTE")
        ).count()
        if _model_has_field(DocumentoKM, "status_recebimento")
        else 0
    )

    total_vinculados = (
        DocumentoKM.objects.filter(
            status_vinculo_ld=getattr(DocumentoKM, "STATUS_VINCULO_LD_AUTO", "AUTO")
        ).count()
        if _model_has_field(DocumentoKM, "status_vinculo_ld")
        else 0
    )

    disciplinas = (
        DocumentoKM.objects.exclude(disciplina="")
        .exclude(disciplina__isnull=True)
        .values_list("disciplina", flat=True)
        .distinct()
        .order_by("disciplina")
        if _model_has_field(DocumentoKM, "disciplina")
        else []
    )

    status_km = (
        DocumentoKM.objects.exclude(status_km="")
        .exclude(status_km__isnull=True)
        .values_list("status_km", flat=True)
        .distinct()
        .order_by("status_km")
        if _model_has_field(DocumentoKM, "status_km")
        else []
    )

    paginator = Paginator(registros, 50)
    page_obj = paginator.get_page(request.GET.get("page"))

    return render(
        request,
        "automacoes/lista_km.html",
        {
            "registros": page_obj,
            "page_obj": page_obj,
            "busca": busca,
            "status": status,
            "disciplina": disciplina,
            "total": total,
            "total_recebidos": total_recebidos,
            "total_pendentes": total_pendentes,
            "total_vinculados": total_vinculados,
            "disciplinas": disciplinas,
            "status_km": status_km,
        },
    )
'''
    views = views.rstrip() + "\n\n" + view_code + "\n"

if 'path("lista-km/"' not in urls:
    anchor = 'path("importar-lista-km/", views.importar_lista_km, name="importar_lista_km"),'
    route = '    path("lista-km/", views.listar_km, name="lista_km"),'
    if anchor not in urls:
        raise SystemExit("Âncora importar-lista-km não encontrada em urls.py")
    urls = urls.replace(anchor, anchor + "\n" + route)

if base_path.exists():
    base = base_path.read_text(encoding="utf-8")

    if "{% url 'automacoes:lista_km' as url_lista_km %}" not in base:
        marker = "{% url 'automacoes:importar_lista_km' as url_importar_lista_km %}"
        if marker in base:
            base = base.replace(marker, marker + "\n{% url 'automacoes:lista_km' as url_lista_km %}")

    if "Lista LD Kongsberg" not in base:
        lista_link = '''
        <li>
          <a class="sidebar-link sidebar-link-km" href="{{ url_lista_km|default:'/automacoes/lista-km/' }}" title="Lista LD Kongsberg">
            <i class="bi bi-table"></i>
            <span class="sidebar-text">Lista LD Kongsberg</span>
          </a>
        </li>'''

        marker = 'title="Importar LD Kongsberg"'
        idx = base.find(marker)
        if idx != -1:
            li_end = base.find("</li>", idx)
            if li_end != -1:
                li_end += len("</li>")
                base = base[:li_end] + lista_link + base[li_end:]
        else:
            marker2 = "Transmittals KM"
            idx = base.find(marker2)
            li_start = base.rfind("<li>", 0, idx) if idx != -1 else -1
            if li_start != -1:
                base = base[:li_start] + lista_link + "\n" + base[li_start:]

    base_path.write_text(base, encoding="utf-8")
else:
    print("AVISO: templates/documentos/base.html não encontrado. Sidebar não alterada.")

template_dir.mkdir(parents=True, exist_ok=True)

template = '''{% extends "documentos/base.html" %}
{% load static %}

{% block title %}Lista LD Kongsberg{% endblock %}

{% block extra_head %}
<link rel="stylesheet" href="{% static 'automacoes/css/ops_enterprise.css' %}?v=1700">
{% endblock %}

{% block content %}
<div class="ops-page">

  <section class="ops-hero">
    <div class="ops-hero-main">
      <div class="ops-eyebrow">
        <span class="ged-status-dot"></span>
        KM DOCUMENT MASTER
      </div>

      <h1>Lista LD Kongsberg</h1>

      <p>
        Consulta operacional da Lista Mestre Kongsberg importada para DocumentoKM,
        com recebimento por Transmittal KM e vínculo com LD Petrobras.
      </p>

      <div class="ops-actions mt-3">
        <a href="{% url 'automacoes:importar_lista_km' %}" class="ops-btn ops-btn-primary">
          <i class="bi bi-cloud-upload"></i>
          Importar LD Kongsberg
        </a>

        <a href="{% url 'automacoes:dashboard_km_ld' %}" class="ops-btn">
          <i class="bi bi-diagram-3"></i>
          Dashboard KM ↔ LD
        </a>

        <a href="{% url 'automacoes:transmittals_km' %}" class="ops-btn">
          <i class="bi bi-box-seam"></i>
          Transmittals KM
        </a>
      </div>
    </div>

    <div class="ops-detail-card">
      <span class="ops-filter-label">Total DocumentoKM</span>
      <strong>{{ total }}</strong>
      <div class="ops-muted mt-2">base importada da LD_KM.</div>
    </div>
  </section>

  <section class="ops-kpi-grid ops-kpi-grid-4 mb-3">
    <div class="ops-kpi">
      <span>Total KM</span>
      <strong>{{ total }}</strong>
      <small>documentos importados</small>
    </div>

    <div class="ops-kpi">
      <span>Recebidos</span>
      <strong>{{ total_recebidos }}</strong>
      <small>com transmittal KM</small>
    </div>

    <div class="ops-kpi">
      <span>Pendentes</span>
      <strong>{{ total_pendentes }}</strong>
      <small>sem recebimento</small>
    </div>

    <div class="ops-kpi">
      <span>Vinculados LD</span>
      <strong>{{ total_vinculados }}</strong>
      <small>match com Petrobras</small>
    </div>
  </section>

  <section class="ops-panel mb-3">
    <form method="get" class="ops-filter-grid">
      <div>
        <label class="ops-filter-label">Buscar</label>
        <input type="text"
               name="q"
               value="{{ busca }}"
               class="form-control"
               placeholder="Número KM, título, disciplina, transmittal...">
      </div>

      <div>
        <label class="ops-filter-label">Disciplina</label>
        <select name="disciplina" class="form-select">
          <option value="">Todas</option>
          {% for item in disciplinas %}
          <option value="{{ item }}" {% if item == disciplina %}selected{% endif %}>{{ item }}</option>
          {% endfor %}
        </select>
      </div>

      <div>
        <label class="ops-filter-label">Status KM</label>
        <select name="status" class="form-select">
          <option value="">Todos</option>
          {% for item in status_km %}
          <option value="{{ item }}" {% if item == status %}selected{% endif %}>{{ item }}</option>
          {% endfor %}
        </select>
      </div>

      <div class="d-flex align-items-end gap-2">
        <button type="submit" class="ops-btn ops-btn-primary w-100">
          <i class="bi bi-funnel"></i>
          Filtrar
        </button>

        <a href="{% url 'automacoes:lista_km' %}" class="ops-btn">
          Limpar
        </a>
      </div>
    </form>
  </section>

  <section class="ops-panel">
    <div class="ops-panel-head">
      <div>
        <h2>Documentos KM</h2>
        <p>Registros importados da aba LD_KM.</p>
      </div>
      <span class="ops-chip">{{ page_obj.paginator.count }} registros filtrados</span>
    </div>

    <div class="table-responsive mt-3">
      <table class="table table-dark table-hover align-middle ops-table">
        <thead>
          <tr>
            <th>Número KM</th>
            <th>Título</th>
            <th>Disciplina</th>
            <th>Status KM</th>
            <th>Transmittal</th>
            <th>Recebimento</th>
            <th>Documento TP</th>
            <th>Vínculo LD</th>
            <th>Score</th>
          </tr>
        </thead>
        <tbody>
          {% for item in registros %}
          <tr>
            <td><strong>{{ item.numero_km }}</strong></td>
            <td>{{ item.titulo|default:"—"|truncatechars:90 }}</td>
            <td>{{ item.disciplina|default:"—" }}</td>
            <td>{{ item.status_km|default:"—" }}</td>
            <td>{{ item.transmittal_numero|default:"—" }}</td>
            <td>{{ item.status_recebimento|default:"—" }}</td>
            <td>{{ item.documento_tp|default:"—" }}</td>
            <td>{{ item.status_vinculo_ld|default:"—" }}</td>
            <td>{{ item.score_vinculo_ld|default:"—" }}</td>
          </tr>
          {% empty %}
          <tr>
            <td colspan="9" class="text-center ops-muted py-4">
              Nenhum documento KM encontrado. Importe a LD Kongsberg primeiro.
            </td>
          </tr>
          {% endfor %}
        </tbody>
      </table>
    </div>

    {% if page_obj.has_other_pages %}
    <div class="d-flex justify-content-between align-items-center mt-3 flex-wrap gap-2">
      <span class="ops-muted">
        Página {{ page_obj.number }} de {{ page_obj.paginator.num_pages }}
      </span>

      <div class="ops-actions">
        {% if page_obj.has_previous %}
        <a class="ops-btn" href="?page={{ page_obj.previous_page_number }}&q={{ busca }}&disciplina={{ disciplina }}&status={{ status }}">
          Anterior
        </a>
        {% endif %}

        {% if page_obj.has_next %}
        <a class="ops-btn" href="?page={{ page_obj.next_page_number }}&q={{ busca }}&disciplina={{ disciplina }}&status={{ status }}">
          Próxima
        </a>
        {% endif %}
      </div>
    </div>
    {% endif %}
  </section>

</div>
{% endblock %}
'''

template_path.write_text(template, encoding="utf-8")
views_path.write_text(views, encoding="utf-8")
urls_path.write_text(urls, encoding="utf-8")

py_compile.compile(str(views_path), doraise=True)

print("OK: Lista LD Kongsberg criada.")
print("Arquivos alterados:")
print("- apps/automacoes/views.py")
print("- apps/automacoes/urls.py")
print("- apps/automacoes/templates/automacoes/lista_km.html")
if base_path.exists():
    print("- templates/documentos/base.html")
print("")
print("Agora rode:")
print("python manage.py check")
print("python manage.py test apps.automacoes apps.contas")
