from django.shortcuts import render, redirect, get_object_or_404
from django.core.files.storage import default_storage
from django.contrib.auth import authenticate, login, logout
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.db.models import Count, Q
from django.utils import timezone
from django.http import HttpResponse
from datetime import date, datetime
from io import BytesIO
import json
import os

import openpyxl
from openpyxl.styles import Font, Alignment, PatternFill, Border, Side
from openpyxl.utils import get_column_letter

from .models import Documento, ImportacaoLDP, WorkflowDocumento, ArquivoDocumento

# =================================================================
# CONFIG GLOBAL
# =================================================================

VALOR_MEDICAO_USD = 979.00
TAXA_CAMBIO_REAIS = 5.76

REVISOES_VALIDAS = [
    "A","B","C","D","E","F","G","H",
    "J","K","L","M","N","P","Q","R",
    "S","T","U","V","W","X","Y","Z",
    "AA","AB","AC","AD","AE","AF","AG","AH",
    "AJ","AK"
]


# =================================================================
# FUNÇÕES AUXILIARES
# =================================================================

def normalizar_revisao(rev_bruto):
    if rev_bruto is None:
        return ""
    rev = str(rev_bruto).strip().upper()

    if rev == "":
        return ""
    if rev == "0":
        return "0"
    if rev.isdigit():
        return None
    if any(ch.isdigit() for ch in rev):
        return None

    if rev.startswith("R") and rev[1:].isalpha():
        return rev[1:]

    return rev if rev.isalpha() else None


def registrar_workflow(documento, etapa, status, request, observacao=""):
    ip = request.META.get("HTTP_X_FORWARDED_FOR")
    ip = ip.split(",")[0].strip() if ip else request.META.get("REMOTE_ADDR", "")
    user_agent = request.META.get("HTTP_USER_AGENT", "")
    meta = f"IP: {ip} | UA: {user_agent[:180]}"
    obs_final = observacao + " | " + meta if observacao else meta

    usuario = request.user.username if request.user.is_authenticated else "Sistema"

    WorkflowDocumento.objects.create(
        documento=documento,
        etapa=etapa,
        status=status,
        usuario=usuario,
        observacao=obs_final,
    )


# =================================================================
# LOGIN / LOGOUT
# =================================================================

def login_view(request):
    if request.method == "POST":
        user = authenticate(
            request,
            username=request.POST.get("username"),
            password=request.POST.get("password"),
        )
        if user:
            login(request, user)
            return redirect("documentos:listar_documentos")

        return render(
            request,
            "registration/login.html",
            {"erro": "Usuário ou senha incorretos."},
        )
    return render(request, "registration/login.html")


def logout_view(request):
    logout(request)
    return redirect("documentos:login")


# =================================================================
# DASHBOARD SIMPLES
# =================================================================

@login_required
def dashboard(request):

    docs = Documento.objects.filter(ativo=True)

    total_docs = docs.count()
    total_aprovados = docs.filter(status_ldp="Aprovado").count()
    total_em_revisao = docs.filter(status_ldp="Em Revisão").count()
    total_emitidos = docs.filter(status_emissao="Emitido").count()
    total_nao_recebidos = docs.filter(status_emissao="Não Recebido").count()

    valor_emitidos_usd = total_emitidos * VALOR_MEDICAO_USD
    valor_emitidos_brl = valor_emitidos_usd * TAXA_CAMBIO_REAIS

    valor_nao_rec_usd = total_nao_recebidos * VALOR_MEDICAO_USD
    valor_nao_rec_brl = valor_nao_rec_usd * TAXA_CAMBIO_REAIS

    valor_total_usd = valor_emitidos_usd + valor_nao_rec_usd
    valor_total_brl = valor_emitidos_brl + valor_nao_rec_brl

    por_disciplina = (
        docs.values("disciplina")
        .exclude(disciplina__isnull=True)
        .exclude(disciplina__exact="")
        .annotate(qtd=Count("id"))
    )

    disc_labels = [d["disciplina"] for d in por_disciplina]
    disc_data = [d["qtd"] for d in por_disciplina]

    por_status = docs.values("status_ldp").annotate(qtd=Count("id"))
    status_labels = [d["status_ldp"] or "Sem Status" for d in por_status]
    status_data = [d["qtd"] for d in por_status]

    return render(
        request,
        "documentos/dashboard.html",
        {
            "total_docs": total_docs,
            "total_aprovados": total_aprovados,
            "total_em_revisao": total_em_revisao,
            "total_emitidos": total_emitidos,
            "total_nao_recebidos": total_nao_recebidos,
            "valor_emitidos_usd": f"{valor_emitidos_usd:,.2f}",
            "valor_emitidos_brl": f"{valor_emitidos_brl:,.2f}",
            "valor_nao_rec_usd": f"{valor_nao_rec_usd:,.2f}",
            "valor_nao_rec_brl": f"{valor_nao_rec_brl:,.2f}",
            "valor_total_usd": f"{valor_total_usd:,.2f}",
            "valor_total_brl": f"{valor_total_brl:,.2f}",
            "disc_labels": json.dumps(disc_labels),
            "disc_data": json.dumps(disc_data),
            "status_labels": json.dumps(status_labels),
            "status_data": json.dumps(status_data),
        },
    )


# =================================================================
# DASHBOARD ENTERPRISE
# =================================================================

@login_required
def dashboard_enterprise(request):
    docs = Documento.objects.filter(ativo=True)

    filtros = {
        "projeto": request.GET.get("projeto") or "",
        "disciplina": request.GET.get("disciplina") or "",
        "tipo_doc": request.GET.get("tipo_doc") or "",
        "status_ldp": request.GET.get("status_ldp") or "",
        "status_emissao": request.GET.get("status_emissao") or "",
        "dt_ini": request.GET.get("dt_ini") or "",
        "dt_fim": request.GET.get("dt_fim") or "",
    }

    # Aplicação dos filtros
    if filtros["projeto"]:
        docs = docs.filter(projeto__icontains=filtros["projeto"])
    if filtros["disciplina"]:
        docs = docs.filter(disciplina=filtros["disciplina"])
    if filtros["tipo_doc"]:
        docs = docs.filter(tipo_doc=filtros["tipo_doc"])
    if filtros["status_ldp"]:
        docs = docs.filter(status_ldp=filtros["status_ldp"])
    if filtros["status_emissao"]:
        docs = docs.filter(status_emissao=filtros["status_emissao"])

    # Data
    if filtros["dt_ini"]:
        dt_ini = datetime.strptime(filtros["dt_ini"], "%Y-%m-%d").date()
        docs = docs.filter(data_emissao_tp__gte=dt_ini)

    if filtros["dt_fim"]:
        dt_fim = datetime.strptime(filtros["dt_fim"], "%Y-%m-%d").date()
        docs = docs.filter(data_emissao_tp__lte=dt_fim)

    total_docs = docs.count()
    total_emitidos = docs.filter(status_emissao="Emitido").count()
    total_nao_recebidos = docs.filter(status_emissao="Não Recebido").count()
    total_em_revisao = docs.filter(status_ldp="Em Revisão").count()
    total_aprovados = docs.filter(status_ldp="Aprovado").count()

    valor_emitidos_usd = total_emitidos * VALOR_MEDICAO_USD
    valor_nao_rec_usd = total_nao_recebidos * VALOR_MEDICAO_USD
    valor_total_usd = valor_emitidos_usd + valor_nao_rec_usd

    valor_emitidos_brl = valor_emitidos_usd * TAXA_CAMBIO_REAIS
    valor_nao_rec_brl = valor_nao_rec_usd * TAXA_CAMBIO_REAIS
    valor_total_brl = valor_emitidos_brl + valor_nao_rec_brl

    por_disc = docs.values("disciplina").annotate(qtd=Count("id"))
    disc_labels = [d["disciplina"] for d in por_disc]
    disc_data = [d["qtd"] for d in por_disc]

    por_status = docs.values("status_ldp").annotate(qtd=Count("id"))
    status_labels = [d["status_ldp"] or "Sem Status" for d in por_status]
    status_data = [d["qtd"] for d in por_status]

    # Medição resumida
    med_raw = docs.values("tipo_doc").annotate(
        total=Count("id"),
        emitidos=Count("id", filter=Q(status_emissao="Emitido")),
        nr=Count("id", filter=Q(status_emissao="Não Recebido")),
    )

    medicao_linhas = []
    total_usd = 0
    total_brl = 0

    for m in med_raw:
        tipo = m["tipo_doc"] or "Sem Tipo"
        emit = m["emitidos"]
        nr = m["nr"]

        v_emit_usd = emit * VALOR_MEDICAO_USD
        v_emit_brl = v_emit_usd * TAXA_CAMBIO_REAIS

        v_nr_usd = nr * VALOR_MEDICAO_USD
        v_nr_brl = v_nr_usd * TAXA_CAMBIO_REAIS

        total_usd += v_emit_usd + v_nr_usd
        total_brl += v_emit_brl + v_nr_brl

        medicao_linhas.append({
            "tipo_doc": tipo,
            "total": m["total"],
            "emitidos": emit,
            "nao_recebidos": nr,
            "valor_emitidos_usd": f"{v_emit_usd:,.2f}",
            "valor_emitidos_brl": f"{v_emit_brl:,.2f}",
            "valor_nr_usd": f"{v_nr_usd:,.2f}",
            "valor_nr_brl": f"{v_nr_brl:,.2f}",
        })

    medicao_totais = {
        "total_docs": sum(m["total"] for m in med_raw),
        "total_usd": f"{total_usd:,.2f}",
        "total_brl": f"{total_brl:,.2f}",
    }

    base_qs = Documento.objects.filter(ativo=True)

    return render(
        request,
        "documentos/dashboard_enterprise.html",
        {
            "filtros": filtros,

            "total_docs": total_docs,
            "total_emitidos": total_emitidos,
            "total_nao_recebidos": total_nao_recebidos,
            "total_em_revisao": total_em_revisao,
            "total_aprovados": total_aprovados,

            "valor_emitidos_usd": f"{valor_emitidos_usd:,.2f}",
            "valor_emitidos_brl": f"{valor_emitidos_brl:,.2f}",
            "valor_nao_rec_usd": f"{valor_nao_rec_usd:,.2f}",
            "valor_nao_rec_brl": f"{valor_nao_rec_brl:,.2f}",
            "valor_total_usd": f"{valor_total_usd:,.2f}",
            "valor_total_brl": f"{valor_total_brl:,.2f}",

            "disc_labels": json.dumps(disc_labels),
            "disc_data": json.dumps(disc_data),
            "status_labels": json.dumps(status_labels),
            "status_data": json.dumps(status_data),

            "medicao_linhas": medicao_linhas,
            "medicao_totais": medicao_totais,

            "lista_projetos": base_qs.values_list("projeto", flat=True).distinct(),
            "lista_disciplinas": base_qs.values_list("disciplina", flat=True).distinct(),
            "lista_tipos": base_qs.values_list("tipo_doc", flat=True).distinct(),
            "lista_status_ldp": base_qs.values_list("status_ldp", flat=True).distinct(),
            "lista_status_emissao": base_qs.values_list("status_emissao", flat=True).distinct(),
        },
    )


# =================================================================
# LISTAR DOCUMENTOS
# =================================================================

@login_required
def listar_documentos(request):
    docs = Documento.objects.all().order_by("-criado_em")

    busca = request.GET.get("busca")
    if busca:
        docs = docs.filter(
            Q(titulo__icontains=busca)
            | Q(codigo__icontains=busca)
            | Q(tipo_doc__icontains=busca)
        )

    return render(
        request,
        "documentos/listar.html",
        {"documentos": docs},
    )


# =================================================================
# DETALHE DO DOCUMENTO
# =================================================================

@login_required
def detalhes_documento(request, documento_id):
    documento = get_object_or_404(Documento, id=documento_id)
    historico = documento.workflow.order_by("-data")

    anexos = documento.arquivos.all()

    # Monta URL absoluta para cada anexo
    for a in anexos:
        try:
            a.url_absoluta = request.build_absolute_uri(a.arquivo.url)
        except:
            a.url_absoluta = a.arquivo.url

    return render(
        request,
        "documentos/detalhes.html",
        {
            "documento": documento,
            "historico_workflow": historico,
            "anexos": anexos
        },
    )

# =================================================================
# UPLOAD MÚLTIPLO DE ARQUIVOS
# =================================================================

@login_required
def adicionar_arquivos(request, documento_id):
    documento = get_object_or_404(Documento, id=documento_id)

    if request.method == "POST":
        arquivos = request.FILES.getlist("arquivos")

        for arq in arquivos:
            ArquivoDocumento.objects.create(
                documento=documento,
                arquivo=arq,
                nome_original=arq.name,
                tipo=arq.name.split(".")[-1].lower()
            )

        registrar_workflow(
            documento,
            "Upload de anexos",
            "Arquivos adicionados",
            request,
            observacao=f"{len(arquivos)} arquivos enviados"
        )

        messages.success(request, "Arquivos enviados com sucesso!")
        return redirect("documentos:detalhes_documento", documento_id=documento_id)

    return render(request, "documentos/adicionar_arquivos.html", {"documento": documento})


# =================================================================
# EXCLUIR ARQUIVO INDIVIDUAL
# =================================================================

@login_required
def excluir_arquivo(request, arquivo_id):
    arq = get_object_or_404(ArquivoDocumento, id=arquivo_id)
    documento_id = arq.documento.id

    try:
        default_storage.delete(arq.arquivo.name)
    except:
        pass

    arq.delete()

    messages.success(request, "Arquivo excluído com sucesso!")
    return redirect("documentos:detalhes_documento", documento_id=documento_id)


# =================================================================
# CRIAÇÃO / UPLOAD DOCUMENTO
# =================================================================

@login_required
def upload_documento(request):

    if request.method == "POST":

        revisao = normalizar_revisao(request.POST.get("revisao"))
        if revisao is None:
            messages.error(request, "Revisão inválida!")
            return redirect("documentos:upload_documento")

        doc = Documento.objects.create(
            titulo=request.POST.get("titulo"),
            codigo=request.POST.get("codigo"),
            revisao=revisao,
            projeto=request.POST.get("projeto"),
            disciplina=request.POST.get("disciplina"),
            tipo_doc=request.POST.get("tipo_doc"),
        )

        # Múltiplos arquivos no upload inicial
        arquivos = request.FILES.getlist("arquivos")
        for arq in arquivos:
            ArquivoDocumento.objects.create(
                documento=doc,
                arquivo=arq,
                nome_original=arq.name,
                tipo=arq.name.split(".")[-1].lower()
            )

        registrar_workflow(doc, "Criação", "Criado", request)

        messages.success(request, "Documento criado com sucesso!")
        return redirect("documentos:listar_documentos")

    return render(request, "documentos/upload.html")


# =================================================================
# EDITAR DOCUMENTO
# =================================================================

@login_required
def editar_documento(request, documento_id):
    documento = get_object_or_404(Documento, id=documento_id)

    if request.method == "POST":
        revisao = normalizar_revisao(request.POST.get("revisao"))
        if revisao is None:
            messages.error(request, "Revisão inválida.")
            return redirect("documentos:editar_documento", documento_id=documento_id)

        for campo in ["projeto", "fase", "tipo_doc", "codigo", "disciplina", "titulo",
                      "status_ldp", "status_emissao", "numero_grdt", "numero_pcf"]:
            setattr(documento, campo, request.POST.get(campo))

        documento.revisao = revisao
        documento.data_emissao_tp = request.POST.get("data_emissao_tp") or None

        documento.save()

        messages.success(request, "Documento atualizado.")
        return redirect("documentos:detalhes_documento", documento_id=documento_id)

    return render(
        request,
        "documentos/editar.html",
        {"documento": documento, "REVISOES_VALIDAS": REVISOES_VALIDAS},
    )


# =================================================================
# NOVA REVISÃO + COPIA ANEXOS SE QUISER
# =================================================================

@login_required
def nova_revisao(request, documento_id):
    original = get_object_or_404(Documento, id=documento_id)

    idx = REVISOES_VALIDAS.index(original.revisao) if original.revisao in REVISOES_VALIDAS else -1
    nova_rev = REVISOES_VALIDAS[idx + 1] if idx + 1 < len(REVISOES_VALIDAS) else "A"

    if request.method == "POST":
        novo = Documento.objects.create(
            titulo=original.titulo,
            codigo=original.codigo,
            revisao=nova_rev,
            projeto=original.projeto,
            disciplina=original.disciplina,
            tipo_doc=original.tipo_doc,
        )

        registrar_workflow(novo, "Nova Revisão", "Criado", request)

        messages.success(request, "Nova revisão criada!")
        return redirect("documentos:detalhes_documento", documento_id=novo.id)

    return render(
        request,
        "documentos/nova_revisao.html",
        {"documento": original, "proxima_revisao": nova_rev},
    )
# =================================================================
# EXCLUIR DOCUMENTOS SELECIONADOS (SOFT DELETE)
# =================================================================

@login_required
def excluir_selecionados(request):
    if request.method != "POST":
        return redirect("documentos:listar_documentos")

    ids = request.POST.getlist("selecionados")

    if not ids:
        messages.warning(request, "Nenhum documento selecionado.")
        return redirect("documentos:listar_documentos")

    docs = Documento.objects.filter(id__in=ids)

    for doc in docs:
        doc.ativo = False
        doc.deletado_por = request.user.username
        doc.deletado_em = timezone.now()
        doc.save()

        registrar_workflow(doc, "Exclusão em lote", "Excluído", request)

    messages.success(request, f"{docs.count()} documentos movidos para a lixeira.")
    return redirect("documentos:listar_documentos")


# =================================================================
# LIXEIRA / EXCLUSÃO
# =================================================================

@login_required
def excluir_documento(request, documento_id):
    doc = get_object_or_404(Documento, id=documento_id)

    doc.ativo = False
    doc.deletado_por = request.user.username
    doc.deletado_em = timezone.now()
    doc.save()

    registrar_workflow(doc, "Exclusão", "Excluído", request)

    messages.success(request, "Documento movido para a lixeira.")
    return redirect("documentos:listar_documentos")


@login_required
def lixeira(request):
    docs = Documento.objects.filter(ativo=False)
    return render(request, "documentos/lixeira.html", {"documentos": docs})


@login_required
def restaurar_documento(request, documento_id):
    doc = get_object_or_404(Documento, id=documento_id)

    doc.ativo = True
    doc.deletado_por = None
    doc.deletado_em = None
    doc.save()

    registrar_workflow(doc, "Restauração", "Restaurado", request)

    messages.success(request, "Documento restaurado!")
    return redirect("documentos:lixeira")

# =================================================================
# HISTÓRICO DE REVISÕES (POR CÓDIGO)
# =================================================================

@login_required
def historico(request, codigo):
    # Todas as revisões do mesmo documento (mesmo código)
    revisoes = Documento.objects.filter(codigo=codigo).order_by("-criado_em")

    if not revisoes.exists():
        messages.error(request, "Nenhum documento encontrado para este código.")
        return redirect("documentos:listar_documentos")

    doc_ref = revisoes.first()

    # Anexos de todas as revisões agrupados
    anexos_por_rev = {
        rev.id: rev.arquivos.all()
        for rev in revisoes
    }

    return render(
        request,
        "documentos/historico.html",
        {
            "documento_ref": doc_ref,
            "revisoes": revisoes,
            "anexos_por_rev": anexos_por_rev,
        },
    )

# =================================================================
# IMPORTAÇÃO LDP 100% REVISADA
# =================================================================

@login_required
def importar_ldp(request):

    contexto = {
        "historico": ImportacaoLDP.objects.all().order_by("-criado_em")[:10]
    }

    if request.method == "POST" and request.FILES.get("arquivo"):

        arq = request.FILES["arquivo"]
        caminho = default_storage.save(f"importacoes/{arq.name}", arq)

        wb = openpyxl.load_workbook(default_storage.open(caminho), data_only=True)
        ws = wb.active

        MAPA = {
            "Projeto": "projeto",
            "Fase": "fase",
            "Tipo de Doc": "tipo_doc",
            "Código": "codigo",
            "Revisão": "revisao",
            "Disciplina": "disciplina",
            "Titulo": "titulo",
            "Status LDP": "status_ldp",
            "Status Emissão": "status_emissao",
            "Nº GRDT de Envio TP": "numero_grdt",
            "Nº PCF": "numero_pcf",
            "Data Emissão TP": "data_emissao_tp",
        }

        header = [c.value for c in ws[1]]
        index = {i: MAPA[c] for i, c in enumerate(header) if c in MAPA}

        total_ok = 0
        total_err = 0
        log = ""

        def conv_data(v):
            if isinstance(v, datetime):
                return v.date()
            try:
                return datetime.strptime(str(v), "%d/%m/%Y").date()
            except:
                return None

        for row in ws.iter_rows(min_row=2, values_only=True):
            dados = {}
            for i, field in index.items():
                valor = row[i]

                if field == "data_emissao_tp":
                    dados[field] = conv_data(valor)
                    continue

                if field == "status_emissao":
                    v = str(valor).strip().title() if valor else ""
                    if v in ["Nr", "NR", "Nao Recebido", "Não recebido"]:
                        v = "Não Recebido"
                    dados[field] = v
                    continue

                dados[field] = valor

            if not dados.get("codigo"):
                continue

            dados["revisao"] = normalizar_revisao(dados.get("revisao")) or ""

            try:
                Documento.objects.update_or_create(
                    codigo=dados["codigo"],
                    defaults=dados
                )
                total_ok += 1

            except Exception as e:
                total_err += 1
                log += f"Erro {dados.get('codigo')}: {e}\n"

        ImportacaoLDP.objects.create(
            arquivo_nome=arq.name,
            total_sucesso=total_ok,
            total_erros=total_err,
            log=log,
        )

        contexto.update({
            "mensagem": "Importado!",
            "total_sucesso": total_ok,
            "total_erros": total_err,
            "log": log,
        })

    return render(request, "documentos/importar_ldp.html", contexto)


# =================================================================
# MEDIÇÃO
# =================================================================

@login_required
def medicao(request):
    docs = Documento.objects.filter(ativo=True)

    med_raw = docs.values("tipo_doc").annotate(
        total=Count("id"),
        emitidos=Count("id", filter=Q(status_emissao="Emitido")),
        nr=Count("id", filter=Q(status_emissao="Não Recebido")),
    )

    linhas = []
    tipos = []
    usd = []
    brl = []

    total_docs = 0
    total_emitidos = 0
    total_nr = 0

    total_emitidos_usd = 0
    total_emitidos_brl = 0
    total_nr_usd = 0
    total_nr_brl = 0

    for m in med_raw:
        tipo = m["tipo_doc"] or "Sem Tipo"
        emit = m["emitidos"]
        nr = m["nr"]

        v_emit_usd = emit * VALOR_MEDICAO_USD
        v_emit_brl = v_emit_usd * TAXA_CAMBIO_REAIS

        v_nr_usd = nr * VALOR_MEDICAO_USD
        v_nr_brl = v_nr_usd * TAXA_CAMBIO_REAIS

        linhas.append({
            "tipo_doc": tipo,
            "total": m["total"],
            "emitidos": emit,
            "nao_recebidos": nr,
            "valor_emitidos_usd": f"{v_emit_usd:,.2f}",
            "valor_emitidos_brl": f"{v_emit_brl:,.2f}",
            "valor_nr_usd": f"{v_nr_usd:,.2f}",
            "valor_nr_brl": f"{v_nr_brl:,.2f}",
        })

        tipos.append(tipo)
        usd.append(float(v_emit_usd + v_nr_usd))
        brl.append(float(v_emit_brl + v_nr_brl))

        total_docs += m["total"]
        total_emitidos += emit
        total_nr += nr

        total_emitidos_usd += v_emit_usd
        total_emitidos_brl += v_emit_brl
        total_nr_usd += v_nr_usd
        total_nr_brl += v_nr_brl

    totais = {
        "total_docs": total_docs,
        "total_emitidos": total_emitidos,
        "total_nao_recebidos": total_nr,
        "total_emitidos_usd": f"{total_emitidos_usd:,.2f}",
        "total_emitidos_brl": f"{total_emitidos_brl:,.2f}",
        "total_nr_usd": f"{total_nr_usd:,.2f}",
        "total_nr_brl": f"{total_nr_brl:,.2f}",
    }

    return render(
        request,
        "documentos/medicao.html",
        {
            "linhas": linhas,
            "totais": totais,
            "TAXA_CAMBIO_REAIS": TAXA_CAMBIO_REAIS,
            "VALOR_MEDICAO_USD": VALOR_MEDICAO_USD,
            "tipos_js": json.dumps(tipos),
            "usd_js": json.dumps(usd),
            "brl_js": json.dumps(brl),
        },
    )


# =================================================================
# EXPORTAÇÃO EXCEL PREMIUM
# =================================================================

@login_required
def exportar_medicao_excel(request):

    wb = openpyxl.Workbook()
    ws = wb.active
    ws.title = "Medição GED"

    # Header
    headers = [
        "Tipo Doc", "Total", "Emitidos", "Não Recebidos",
        "Valor Emitidos (USD)", "Valor Emitidos (BRL)",
        "Valor Não Recebidos (USD)", "Valor Não Recebidos (BRL)"
    ]
    ws.append(headers)

    header_fill = PatternFill(start_color="00C8FF", end_color="00C8FF", fill_type="solid")
    border = Border(left=Side(style="thin"), right=Side(style="thin"),
                    top=Side(style="thin"), bottom=Side(style="thin"))

    for col in ws[1]:
        col.fill = header_fill
        col.font = Font(bold=True)
        col.border = border

    docs = Documento.objects.filter(ativo=True)

    med_raw = docs.values("tipo_doc").annotate(
        total=Count("id"),
        emitidos=Count("id", filter=Q(status_emissao="Emitido")),
        nr=Count("id", filter=Q(status_emissao="Não Recebido")),
    )

    for m in med_raw:
        tipo = m["tipo_doc"] or "Sem Tipo"
        emit = m["emitidos"]
        nr = m["nr"]

        v_emit_usd = emit * VALOR_MEDICAO_USD
        v_emit_brl = v_emit_usd * TAXA_CAMBIO_REAIS
        v_nr_usd = nr * VALOR_MEDICAO_USD
        v_nr_brl = v_nr_usd * TAXA_CAMBIO_REAIS

        ws.append([
            tipo, m["total"], emit, nr,
            v_emit_usd, v_emit_brl, v_nr_usd, v_nr_brl
        ])

    output = BytesIO()
    wb.save(output)
    output.seek(0)

    return HttpResponse(
        output.getvalue(),
        content_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={"Content-Disposition": 'attachment; filename="medicao_ged.xlsx"'},
    )
# =================================================================
# WORKFLOW DO DOCUMENTO (APROVAR / REVISAR / EMITIR / CANCELAR)
# =================================================================

@login_required
def enviar_para_revisao(request, documento_id):
    doc = get_object_or_404(Documento, id=documento_id)

    doc.status_ldp = "Em Revisão"
    doc.save()

    registrar_workflow(doc, "Envio para Revisão", "Em Revisão", request)

    messages.success(request, "Documento enviado para revisão.")
    return redirect("documentos:detalhes_documento", documento_id=documento.id)


@login_required
def aprovar_documento(request, documento_id):
    doc = get_object_or_404(Documento, id=documento_id)

    doc.status_ldp = "Aprovado"
    doc.save()

    registrar_workflow(doc, "Aprovação", "Aprovado", request)

    messages.success(request, "Documento aprovado.")
    return redirect("documentos:detalhes_documento", documento_id=documento.id)


@login_required
def emitir_documento(request, documento_id):
    doc = get_object_or_404(Documento, id=documento_id)

    doc.status_emissao = "Emitido"
    doc.data_emissao_tp = date.today()
    doc.save()

    registrar_workflow(doc, "Emissão", "Emitido", request)

    messages.success(request, "Documento emitido.")
    return redirect("documentos:detalhes_documento", documento_id=documento.id)


@login_required
def cancelar_documento(request, documento_id):
    doc = get_object_or_404(Documento, id=documento_id)

    doc.status_ldp = "Cancelado"
    doc.status_emissao = "Cancelado"
    doc.save()

    registrar_workflow(doc, "Cancelamento", "Cancelado", request)

    messages.success(request, "Documento cancelado.")
    return redirect("documentos:detalhes_documento", documento_id=documento.id)
