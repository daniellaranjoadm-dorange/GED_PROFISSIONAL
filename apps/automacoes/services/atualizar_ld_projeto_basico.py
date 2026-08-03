import os
import shutil
from datetime import datetime, timedelta, date
import xlwings as xw
import re
import threading
import time
from openpyxl import load_workbook
from django.db import transaction

from apps.automacoes.models import DocumentoLD


# ==========================================================
# CONFIGURAÇÕES
# ==========================================================
PLANILHA = r"\\virm-rgr022\FILESERVER\Projetos\05_HANDYMAX\09. Doc Control\3 - LD\I-LD-4880.00-9311-000-CZ1-001_RD.xlsm"
PLANILHA_MARENOVA_EXECUTIVO = r"\\virm-rgr022\FILESERVER\Projetos\05_HANDYMAX\09. Doc Control\3 - LD\I-LD-4880.00-9311-000-CZ1-002_R0.xlsx"

ABA_LD = "LD"
ABA_LD_MARENOVA = "LD MARENOVA"
ABA_LD_BASICO = "LD PROJETO BASICO"
ABA_LD_MARENOVA_EXECUTIVO = "LD MARENOVA P EXECUTIVO"
ABA_GENERAL_LIST_KM = "GENERAL LIST KM"
ABA_MEDICAO = "MEDIÇÃO"  # exatamente como está no Excel

PASTA_DOCS = r"\\virm-rgr022\FILESERVER\Projetos\05_HANDYMAX\09. Doc Control\10 - Engenharia"
PASTA_GRD = r"\\virm-rgr022\FILESERVER\Projetos\05_HANDYMAX\09. Doc Control\1 - DOCS EMISSÃO ENGEDOC\Emitidos"
PASTA_PCF = r"\\virm-rgr022\FILESERVER\Projetos\05_HANDYMAX\09. Doc Control\9 - PCFs Transpetro"
PASTA_PCF_RESPOSTA = r"\\virm-rgr022\FILESERVER\Projetos\05_HANDYMAX\09. Doc Control\9 - PCFs Transpetro\Respostas PCFs MARENOVA"

TIMELINE_PCF = r"\\virm-rgr022\FILESERVER\Projetos\05_HANDYMAX\09. Doc Control\9 - PCFs Transpetro\Timeline PCFs Transpetro.xlsx"

PASTA_LOGS = r"\\virm-rgr022\FILESERVER\Projetos\05_HANDYMAX\09. Doc Control\3 - LD\Logs"
PASTA_BACKUPS = os.path.join(PASTA_LOGS, "Backups")

EXTENSOES = {".doc", ".docx", ".pdf", ".dwg", ".xls", ".xlsx", ".xlsm"}

# ==========================================================
# AJUSTES IMPORTANTES (toggle)
# ==========================================================
# ✅ LOG detalhado (mostra qual arquivo/pasta foi usado em J/K/L/M/O/P/Q)
LOG_DETALHADO = True

# ✅ Como preencher a coluna K (data):
# "DOC" = data do arquivo encontrado dentro do GRD (mais fiel)
# "GRD" = data da pasta GRD (pode mudar se mexerem na pasta depois)
DATA_K_ORIGEM = "DOC"

# ✅ Origem de data para PCF (colunas M e P)
# "MTIME" = data de modificação do arquivo (padrão)
# "CTIME" = data de criação do arquivo (no Windows costuma ser a criação)
DATA_PCF_ORIGEM = "MTIME"
DATA_PCF_RESP_ORIGEM = "MTIME"

# ✅ Preenchimento das colunas de DATA (sem “apagar código”)
# "DATA"   -> escreve a data
# "OBS"    -> escreve uma observação (texto) e NÃO grava data
# "MANTER" -> não mexe no valor atual da célula
COL_K_MODO = "DATA"
COL_M_MODO = "DATA"
COL_P_MODO = "DATA"

OBS_COL_K = "VERIFICAR DATA GRD"
OBS_COL_M = "VERIFICAR DATA PCF"
OBS_COL_P = "VERIFICAR DATA RESPOSTA"

# ✅ Congelar painéis (você disse que está salvando com painéis congelados)
FREEZE_PANES = False

# ✅ Formatação
APLICAR_FORMATACAO = True
ULTIMA_COLUNA = "BD"  # cobre também a última coluna operacional da LD principal

# Excel constants
xlCenter = -4108
xlLeft = -4131

# ✅ Formato de data desejado no Excel PT-BR (para não aparecer yyyy)
DATE_NUMBERFORMAT_LOCAL = "dd/mm/aaaa"
DATE_NUMBERFORMAT_FALLBACK = "dd/mm/yyyy"  # formato invariável do Excel


# ==========================================================
# LAYOUTS DE COLUNAS
# ==========================================================
# A rotina original usa o layout da LD principal. Para o piloto do Projeto
# Básico, mantemos a lógica e trocamos apenas a camada de mapeamento.
LAYOUT_LD = {
    "documento": "B",
    "revisao": "C",
    "titulo": "D",
    "disciplina": "E",
    "disciplina_alt": "F",
    "status": "H",
    "status_grd": "I",
    "grd": "J",
    "data_grd": "K",
    "pcf": "L",
    "data_pcf": "M",
    "status_pcf": "N",
    "pcf_resposta": "O",
    "data_resposta": "P",
    "grd_resposta": "Q",
    "numero_documento_km": "AN",
    "km_title": "",
    "transmittal_km": "AO",
    "data_recebimento_km": "AP",
    "casco": "AS",
    "qtd_comentarios": "AV",
    "open_comments": "AW",
    "under_review": "AX",
    "status_final_pcf": "AY",
    "posted_date": "AZ",
    "status_bv": "BA",
    "since_bv": "BB",
    "action_bv": "BC",
    "nb_pending_comments": "BD",
}

LAYOUT_PROJETO_BASICO = {
    "documento": "C",
    "revisao": "D",
    "titulo": "E",
    "disciplina": "G",
    "disciplina_alt": "F",

    # H:K permanecem no mesmo lugar.
    "numero_documento_km": "H",
    "km_title": "I",
    "transmittal_km": "J",
    "data_recebimento_km": "K",

    # Nova coluna inserida no layout.
    # Ela é preservada pela atualização e não é sobrescrita pelo motor.
    "documento_km_emitido_tp": "L",

    # Todas as colunas que estavam a partir de L foram deslocadas +1.
    "status": "M",
    "status_grd": "N",
    "grd": "W",
    "data_grd": "X",
    "pcf": "Y",
    "data_pcf": "Z",
    "status_pcf": "AA",
    "pcf_resposta": "AB",
    "data_resposta": "AC",
    "grd_resposta": "AD",

    "qtd_comentarios": "AE",
    "open_comments": "AF",
    "under_review": "AG",
    "status_final_pcf": "AH",

    "posted_date": "AX",
    "status_bv": "AY",
    "since_bv": "AZ",
    "action_bv": "BA",
    "nb_pending_comments": "BB",
    "casco": "BC",
}

LAYOUT_MARENOVA_EXECUTIVO = {
    "documento": "B",
    "numero_interno": "C",
    "revisao": "D",
    "titulo": "E",
    "disciplina": "F",
    "disciplina_alt": "G",
    "status": "I",
    "status_grd": "J",
    "grd": "K",
    "data_grd": "L",
    "pcf": "M",
    "data_pcf": "N",
    "status_pcf": "O",
    "pcf_resposta": "P",
    "data_resposta": "Q",
    "grd_resposta": "R",
    "numero_documento_km": "",
    "km_title": "",
    "transmittal_km": "",
    "data_recebimento_km": "",
    "casco": "",
    "qtd_comentarios": "",
    "open_comments": "",
    "under_review": "",
    "status_final_pcf": "O",
    "posted_date": "",
    "status_bv": "",
    "since_bv": "",
    "action_bv": "",
    "nb_pending_comments": "",
}

LAYOUTS_ABAS = {
    ABA_LD: LAYOUT_LD,
    ABA_LD_BASICO: LAYOUT_PROJETO_BASICO,
    ABA_LD_MARENOVA_EXECUTIVO: LAYOUT_MARENOVA_EXECUTIVO,
}


def _layout_para_aba(aba_nome, layout=None):
    if layout:
        return layout
    return LAYOUTS_ABAS.get(aba_nome, LAYOUT_LD)


def _col_layout(layout, campo):
    return (layout or {}).get(campo, "") or ""


def _cell_layout(ws, layout, campo, row):
    col = _col_layout(layout, campo)
    if not col:
        return None
    return ws[f"{col}{row}"]


def _valor_layout(ws, layout, campo, row, default=""):
    cell = _cell_layout(ws, layout, campo, row)
    if cell is None:
        return default
    try:
        return cell.value
    except Exception:
        return default


def _set_layout(ws, layout, campo, row, valor):
    cell = _cell_layout(ws, layout, campo, row)
    if cell is not None:
        cell.value = valor
    return cell


def _limpar_hyperlink_layout(ws, layout, campo, row):
    cell = _cell_layout(ws, layout, campo, row)
    if cell is not None:
        limpar_hyperlink(cell)


def _setar_hyperlink_layout(ws, layout, campo, row, endereco, texto):
    cell = _cell_layout(ws, layout, campo, row)
    if cell is not None:
        return setar_hyperlink(cell, endereco, texto)
    return False


# ==========================================================
# LOG
# ==========================================================
LOG_FILE = None  # será definido no processar()

# ==========================================================
# PROGRESSO RUNTIME LD (para UI / polling)
# ==========================================================
_PROGRESSO_LOCK = threading.Lock()
PROGRESSO_LD = {
    "status": "idle",
    "percentual": 0,
    "etapa": "Aguardando execução.",
    "mensagem": "Aguardando execução da Atualização LD.",
    "iniciado_em": "",
    "finalizado_em": "",
    "erro": "",
}


def atualizar_progresso_ld(percentual=None, etapa=None, status=None, mensagem=None, erro=None):
    """Atualiza o estado de progresso da Atualização LD para leitura pela interface."""
    with _PROGRESSO_LOCK:
        if percentual is not None:
            try:
                PROGRESSO_LD["percentual"] = max(0, min(100, int(percentual)))
            except Exception:
                pass

        if etapa is not None:
            PROGRESSO_LD["etapa"] = str(etapa)

        if status is not None:
            PROGRESSO_LD["status"] = str(status)

        if mensagem is not None:
            PROGRESSO_LD["mensagem"] = str(mensagem)

        if erro is not None:
            PROGRESSO_LD["erro"] = str(erro)

        if status == "running" and not PROGRESSO_LD.get("iniciado_em"):
            PROGRESSO_LD["iniciado_em"] = datetime.now().strftime("%d/%m/%Y %H:%M:%S")
            PROGRESSO_LD["finalizado_em"] = ""
            PROGRESSO_LD["erro"] = ""

        if status in {"done", "error", "blocked", "cancelado"}:
            PROGRESSO_LD["finalizado_em"] = datetime.now().strftime("%d/%m/%Y %H:%M:%S")

    return obter_progresso_ld()


def obter_progresso_ld():
    """Retorna uma cópia segura do progresso atual."""
    with _PROGRESSO_LOCK:
        return dict(PROGRESSO_LD)


def resetar_progresso_ld():
    """Reseta o progresso antes de uma nova execução."""
    with _PROGRESSO_LOCK:
        PROGRESSO_LD.update({
            "status": "idle",
            "percentual": 0,
            "etapa": "Aguardando execução.",
            "mensagem": "Aguardando execução da Atualização LD.",
            "iniciado_em": "",
            "finalizado_em": "",
            "erro": "",
        })
    return obter_progresso_ld()


def log(msg: str):
    print(msg)
    if LOG_FILE:
        try:
            with open(LOG_FILE, "a", encoding="utf-8") as f:
                f.write(msg + "\n")
        except Exception:
            pass

def _fmt_dt(dt):
    if not dt:
        return "-"
    try:
        return dt.strftime("%d/%m/%Y %H:%M:%S")
    except Exception:
        return str(dt)

# ==========================================================
# BACKUP
# ==========================================================
def backup_arquivo(caminho):
    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    nome, ext = os.path.splitext(os.path.basename(caminho))
    destino = os.path.join(PASTA_BACKUPS, f"{nome}_BK_{ts}{ext}")
    shutil.copy2(caminho, destino)
    log(f"🔒 Backup criado: {destino}")
    return destino


def backup_planilha():
    return backup_arquivo(PLANILHA)

# ==========================================================
# DATA HELPERS (garante data real + dd/mm/aaaa)
# ==========================================================
def _coerce_to_date(v):
    """Converte o que vier (datetime/date/str/serial) para date, quando possível."""
    if v in (None, ""):
        return None

    if isinstance(v, datetime):
        return v.date()

    if isinstance(v, date):
        return v

    # Excel pode retornar serial float em alguns casos
    if isinstance(v, (int, float)):
        try:
            base = datetime(1899, 12, 30)  # base compatível com Excel
            return (base + timedelta(days=float(v))).date()
        except Exception:
            return None

    if isinstance(v, str):
        s = v.strip()
        if not s:
            return None
        for fmt in (
            "%d/%m/%Y",
            "%d/%m/%y",
            "%d/%m/%Y %H:%M:%S",
            "%d/%m/%y %H:%M:%S",
            "%Y-%m-%d",
            "%Y-%m-%d %H:%M:%S",
            "%Y-%m-%dT%H:%M:%S",
        ):
            try:
                return datetime.strptime(s, fmt).date()
            except Exception:
                pass
        return None

    return None

def _aplicar_formato_data(cell):
    """Aplica formato de data real no Excel sem deixar 'yyyy' literal."""
    try:
        cell.api.NumberFormat = DATE_NUMBERFORMAT_FALLBACK
    except Exception:
        pass

    try:
        cell.api.NumberFormatLocal = DATE_NUMBERFORMAT_LOCAL
    except Exception:
        pass

def setar_data(cell, v):
    """Escreve data como data REAL no Excel e força formato dd/mm/aaaa (PT-BR)."""
    d = _coerce_to_date(v)
    if d is None:
        cell.value = None
        return
    # Grava pelo serial nativo do Excel para não depender da interpretação
    # regional do COM/xlwings. Atribuir "10/04/2026" como texto pode ser
    # interpretado como 4 de outubro em ambientes configurados em inglês.
    serial_excel = (d - date(1899, 12, 30)).days
    try:
        cell.api.Value2 = serial_excel
    except Exception:
        cell.value = datetime(d.year, d.month, d.day)
    _aplicar_formato_data(cell)

def forcar_numberformat_coluna(ws, col_letter, start_row, end_row):
    """Força formato de data real no Excel sem exibir 'yyyy' literal."""
    if end_row < start_row:
        return

    rng = ws.range(f"{col_letter}{start_row}:{col_letter}{end_row}")

    try:
        rng.api.NumberFormat = DATE_NUMBERFORMAT_FALLBACK
    except Exception:
        pass

    try:
        rng.api.NumberFormatLocal = DATE_NUMBERFORMAT_LOCAL
    except Exception:
        pass

def _file_datetime(path: str, origem: str) -> datetime | None:
    """Retorna datetime do arquivo conforme origem (MTIME/CTIME)."""
    try:
        if origem.upper() == "CTIME":
            return datetime.fromtimestamp(os.path.getctime(path))
        return datetime.fromtimestamp(os.path.getmtime(path))
    except Exception:
        return None

# ==========================================================
# NORMALIZAR REV
# ==========================================================
def normalizar_rev(v):
    if v is None:
        return ""
    if isinstance(v, (int, float)):
        return str(int(v))

    s = str(v).strip().upper()
    if s.startswith("R"):
        s = s[1:].strip()

    if s.isdigit():
        return str(int(s))

    return s


def normalizar_codigo(v):
    """Normaliza códigos vindos do Excel e de nomes de arquivo para comparação."""
    s = str(v or "").strip().upper()
    for hifen in ("–", "—", "−", "‐", "‑"):
        s = s.replace(hifen, "-")
    return re.sub(r"\s+", "", s)

def rev_key(rev: str):
    s = (rev or "").strip().upper()
    if s.isdigit():
        return (0, int(s))
    if s.isalpha():
        n = 0
        for ch in s:
            n = n * 26 + (ord(ch) - ord('A') + 1)
        return (1, n)
    return (2, s)

def _suffix_key(s: str) -> int:
    s = (s or "").strip().upper()
    if s == "":
        return -1
    if s.isalpha():
        n = 0
        for ch in s:
            n = n * 26 + (ord(ch) - ord('A') + 1)
        return n
    return -1

def _split_by_base(rev_pcf: str, base: str) -> tuple[bool, str]:
    rev_pcf = (rev_pcf or "").strip().upper()
    base = (base or "").strip().upper()
    if not base or not rev_pcf:
        return (False, "")
    if rev_pcf == base:
        return (True, "")
    if rev_pcf.startswith(base):
        return (True, rev_pcf[len(base):])
    return (False, "")


def _pcf_resposta_da_recebida(rev_recebida: str, base: str) -> str:
    """Retorna a revisao da resposta correspondente a PCF recebida.

    A sequencia do formulario alterna Owner/Builder:
    R0 -> R0A, R0B -> R0C, R0D -> R0E, e assim por diante.
    """
    compativel, sufixo = _split_by_base(rev_recebida, base)
    if not compativel:
        return ""

    if not sufixo:
        proximo = 1
    elif sufixo.isalpha():
        proximo = _suffix_key(sufixo) + 1
    else:
        return ""

    letras = ""
    while proximo > 0:
        proximo, resto = divmod(proximo - 1, 26)
        letras = chr(ord("A") + resto) + letras
    return f"{base}{letras}"


def _revisao_pcf_do_nome(valor) -> str:
    """Extrai a revisão completa de PCF-..._R<base><sufixo>."""
    nome = os.path.basename(str(valor or "").strip())
    nome = re.sub(r"\.(?:XLSX|XLSM)$", "", nome, flags=re.IGNORECASE)
    m = re.search(r"_R([0-9A-Z]+)", nome, re.IGNORECASE)
    return normalizar_rev(m.group(1)) if m else ""

# ==========================================================
# EXTRAIR GRD DO CAMINHO
# ==========================================================
def extrair_grd_do_caminho(path):
    m = re.search(r"(GRD-\d+)", path, re.I)
    return m.group(1).upper() if m else ""

# ==========================================================
# HELPERS (HYPERLINK)
# ==========================================================
def normalizar_endereco_hyperlink(endereco):
    """
    Garante que caminhos UNC sejam gravados no Excel como caminho de rede normal,
    sem prefixo file:///.
    """
    s = str(endereco or "").strip()

    if not s:
        return ""

    s = s.replace("%20", " ")
    lower = s.lower()

    if lower.startswith("file:///"):
        s = s[8:]
    elif lower.startswith("file://"):
        s = s[7:]
    elif lower.startswith("file:/"):
        s = s[6:]

    # Remove uma barra inicial indevida antes de caminho UNC.
    while s.startswith("/") and not s.startswith("//"):
        s = s[1:]

    # Converte //servidor/pasta para \\servidor\pasta.
    if s.startswith("//"):
        s = "\\\\" + s.lstrip("/").replace("/", "\\")

    # Preserva caminhos UNC já corretos.
    return s


def limpar_hyperlink(cell):
    try:
        cell.api.Hyperlinks.Delete()
    except Exception:
        pass

def setar_hyperlink(cell, endereco, texto):
    r"""
    Cria hyperlink preservando caminho UNC de rede.

    Evita links quebrados do tipo file:///\\servidor\pasta\arquivo.xlsx.
    """
    limpar_hyperlink(cell)

    endereco_limpo = normalizar_endereco_hyperlink(endereco)
    cell.value = texto

    if not endereco_limpo:
        return False

    try:
        cell.api.Hyperlinks.Add(
            Anchor=cell.api,
            Address=endereco_limpo,
            TextToDisplay=str(texto or "")
        )
    except Exception:
        try:
            cell.add_hyperlink(endereco_limpo, texto)
        except Exception:
            return False

    try:
        return bool(cell.api.Hyperlinks.Count)
    except Exception:
        return False


# ==========================================================
# HELPERS (AUTOFILTER)
# ==========================================================
def capturar_autofiltro(ws):
    """Captura o AutoFilter atual (range + critérios simples) para restaurar no final."""
    try:
        af = ws.api.AutoFilter
        if af is None:
            return None
        rng = af.Range
        if rng is None:
            return None
        state = {"has_autofilter": True, "range": rng.Address, "criteria": []}

        try:
            filters = af.Filters
            for i in range(1, filters.Count + 1):
                f = filters.Item(i)
                try:
                    on = bool(f.On)
                except Exception:
                    on = False
                if not on:
                    continue

                c1 = None
                c2 = None
                op = None
                try:
                    c1 = f.Criteria1
                except Exception:
                    pass
                try:
                    op = f.Operator
                except Exception:
                    pass
                try:
                    c2 = f.Criteria2
                except Exception:
                    pass

                state["criteria"].append((i, c1, op, c2))
        except Exception:
            pass

        return state
    except Exception:
        return None

def remover_autofiltro(ws):
    try:
        if ws.api.AutoFilterMode:
            ws.api.AutoFilterMode = False
    except Exception:
        pass

def restaurar_autofiltro(ws, state):
    if not state or not state.get("has_autofilter") or not state.get("range"):
        return
    try:
        rng = ws.api.Range(state["range"])
        try:
            rng.AutoFilter()
        except Exception:
            pass

        for field, c1, op, c2 in state.get("criteria", []):
            try:
                if c2 not in (None, ""):
                    rng.AutoFilter(Field=field, Criteria1=c1, Operator=op, Criteria2=c2)
                elif op not in (None, 0, ""):
                    rng.AutoFilter(Field=field, Criteria1=c1, Operator=op)
                else:
                    rng.AutoFilter(Field=field, Criteria1=c1)
            except Exception:
                pass
    except Exception:
        pass

def garantir_autofiltro(ws):
    """
    Garante que a aba fique com setinhas de filtro no cabeçalho (linha 1).
    Útil quando não havia estado capturado/restaurável ou quando a restauração falha.
    """
    try:
        if ws.api.AutoFilterMode:
            return
    except Exception:
        pass

    try:
        ws.range(f"A1:{ULTIMA_COLUNA}1").api.AutoFilter()
    except Exception:
        try:
            ws.api.Range("A1").CurrentRegion.AutoFilter()
        except Exception:
            pass

# ==========================================================
# INDEXADORES
# ==========================================================
def indexar_engenharia_info():
    """
    Retorna:
      idx[codigo][rev] = { "path": pasta_onde_achou, "file": arquivo, "date": mtime_arquivo }
    Se encontrar duplicado (mesmo codigo+rev em lugares diferentes), mantém o mais recente.
    """
    ultimo_erro = None

    for tentativa in range(1, 4):
        idx = {}
        erros_walk = []

        if not os.path.isdir(PASTA_DOCS):
            ultimo_erro = RuntimeError(f"Pasta Engenharia indisponível: {PASTA_DOCS}")
        else:
            for root, _, files in os.walk(PASTA_DOCS, onerror=erros_walk.append):
                for f in files:
                    nome, ext = os.path.splitext(f)
                    if ext.lower() not in EXTENSOES:
                        continue

                    marcador = nome.upper().find("_R")
                    if marcador < 0:
                        continue

                    codigo = normalizar_codigo(nome[:marcador])
                    resto = nome[marcador + 2:]
                    mrev = re.match(r"([0-9A-Z]+)", str(resto).strip().upper())
                    if not mrev:
                        continue

                    rev = normalizar_rev(mrev.group(1))
                    if not codigo or not rev:
                        continue

                    full = os.path.join(root, f)
                    dt = _file_datetime(full, "MTIME")
                    existente = idx.get(codigo, {}).get(rev)
                    data_existente = existente.get("date") if existente else None
                    escolher = (
                        existente is None
                        or (dt is not None and data_existente is None)
                        or (dt is not None and data_existente is not None and dt > data_existente)
                    )
                    if escolher:
                        idx.setdefault(codigo, {})[rev] = {
                            "path": root,
                            "file": full,
                            "date": dt,
                        }

            if idx and not erros_walk:
                return idx

            detalhes = "; ".join(str(e) for e in erros_walk[:3]) or "nenhum documento indexado"
            ultimo_erro = RuntimeError(
                f"Indexação incompleta da Engenharia na tentativa {tentativa}: {detalhes}"
            )

        if tentativa < 3:
            log(f"⚠️ {ultimo_erro}. Nova tentativa em 2 segundos.")
            time.sleep(2)

    raise ultimo_erro or RuntimeError("Falha desconhecida ao indexar a Engenharia.")

def indexar_grds():
    """
    ✅ J: link para a pasta raiz do GRD (GRD-XXXX)
    ✅ K: data conforme DATA_K_ORIGEM:
        - "DOC" => mtime do arquivo encontrado dentro do GRD (recomendado)
        - "GRD" => mtime da pasta raiz do GRD
    """
    idx = {}
    for root, _, files in os.walk(PASTA_GRD):
        grd = extrair_grd_do_caminho(root)
        if not grd:
            continue

        # tentar apontar para a pasta raiz do GRD
        grd_dir = os.path.join(PASTA_GRD, grd)
        if not os.path.isdir(grd_dir):
            grd_dir = root  # fallback

        dt_grd = None
        try:
            dt_grd = datetime.fromtimestamp(os.path.getmtime(grd_dir))
        except Exception:
            dt_grd = None

        for f in files:
            nome = os.path.splitext(f)[0]
            if "_R" not in nome:
                continue

            codigo, resto = nome.split("_R", 1)
            mrev = re.match(r"([0-9A-Z]+)", resto.strip().upper())
            if not mrev:
                continue

            rev = normalizar_rev(mrev.group(1))
            full = os.path.join(root, f)

            dt_doc = _file_datetime(full, "MTIME")
            if DATA_K_ORIGEM.upper() == "GRD" and dt_grd:
                dt_k = dt_grd
            else:
                dt_k = dt_doc or dt_grd

            codigo = normalizar_codigo(codigo)
            existente = idx.get(codigo, {}).get(rev)

            # se houver duplicado, fica com o mais recente (dt_k)
            if existente is None:
                escolher = True
            else:
                ex_dt = existente.get("date")
                escolher = (dt_k and ex_dt and dt_k > ex_dt) or (ex_dt is None and dt_k is not None)

            if escolher:
                idx.setdefault(codigo, {})[rev] = {
                    "grd": grd,
                    "path": grd_dir,
                    "date": dt_k,
                    "doc_file": full,   # para LOG detalhado
                    "doc_dt": dt_doc,
                    "grd_dt": dt_grd
                }
    return idx

def indexar_pcfs(pasta, excluir_subpastas=None, data_origem="MTIME"):
    """
    ✅ Indexa PCFs (L/M ou O/P).
    - excluir_subpastas: lista de subpastas que NÃO devem entrar no index.
    - se existir duplicado (mesmo código+rev), fica com o mais recente (mtime/ctime).
    """
    idx = {}
    excluir_subpastas = excluir_subpastas or []
    excluir_norm = [os.path.normpath(p).lower() for p in excluir_subpastas]

    for root, _, files in os.walk(pasta):
        root_norm = os.path.normpath(root).lower()
        if any(root_norm.startswith(p) for p in excluir_norm):
            continue

        for f in files:
            nome, ext = os.path.splitext(f)
            if ext.lower() not in (".xlsx", ".xlsm"):
                continue
            if not nome.upper().startswith("PCF-"):
                continue
            if "_R" not in nome:
                continue

            base = nome[4:]
            codigo, resto = base.split("_R", 1)
            mrev = re.match(r"([0-9A-Z]+)", resto.strip().upper())
            if not mrev:
                continue

            rev = normalizar_rev(mrev.group(1))
            caminho = os.path.join(root, f)
            # A data oficial da PCF fica no cabeçalho do próprio formulário.
            # MTIME/CTIME é apenas fallback: a data do arquivo muda quando ele é
            # copiado, salvo novamente ou movimentado na rede.
            dt = _pcf_data_documental_arquivo(caminho) or _file_datetime(caminho, data_origem)

            codigo = normalizar_codigo(codigo)
            existente = idx.get(codigo, {}).get(rev)
            info = {
                "pcf": nome,
                "path": caminho,
                "date": dt,
                "rev": rev
            }

            if (existente is None) or (dt and dt > existente["date"]):
                idx.setdefault(codigo, {})[rev] = info
    return idx

def indexar_grd_resposta_pcf():
    """
    Mapeia PCF-*.xls[xm] -> GRD-XXXX (para preencher coluna Q)
    """
    idx = {}
    for root, _, files in os.walk(PASTA_GRD):
        grd = extrair_grd_do_caminho(root)
        if not grd:
            continue

        for f in files:
            nome, ext = os.path.splitext(f)
            if ext.lower() not in (".xlsx", ".xlsm"):
                continue
            if nome.upper().startswith("PCF-"):
                idx[nome.upper()] = grd
    return idx


# ==========================================================
# STATUS FINAL PCF (Timeline PCFs)
# ==========================================================
def normalizar_chave_pcf(v):
    """
    Mantém a chave exatamente como aparece na célula, apenas removendo espaços
    no começo/fim.

    Regra solicitada:
      LD coluna L  ==  Timeline PCFs / aba "PCFs Recebidas TP" / coluna B

    Não remove extensão, não remove revisão, não converte para maiúsculo
    e não faz busca parcial.
    """
    return str(v or "").strip()



def _normalizar_header(valor):
    """Normaliza cabeçalhos/status de PCFs para comparação segura."""
    if valor is None:
        return ""

    texto = str(valor).strip().upper()
    if not texto:
        return ""

    texto = texto.replace("\n", " ").replace("\r", " ")
    texto = (
        texto.replace("Á", "A")
        .replace("À", "A")
        .replace("Â", "A")
        .replace("Ã", "A")
        .replace("É", "E")
        .replace("Ê", "E")
        .replace("Í", "I")
        .replace("Ó", "O")
        .replace("Ô", "O")
        .replace("Õ", "O")
        .replace("Ú", "U")
        .replace("Ç", "C")
    )
    texto = re.sub(r"\s+", " ", texto).strip()
    return texto


def _valor_intel(valor):
    """Preserva valores de inteligência da PCF em formato seguro para Excel."""
    if valor is None:
        return ""

    if isinstance(valor, float):
        return int(valor) if valor.is_integer() else valor

    if isinstance(valor, int):
        return valor

    return str(valor).strip()


def _pcf_intel_tem_valor(intel: dict) -> bool:
    if not isinstance(intel, dict):
        return False
    return any(str(intel.get(k, "")).strip() for k in ("qtd_comentarios", "open_comments", "under_review", "status_final"))


def _intel_num(valor):
    """Converte valores de comentários para número quando possível, preservando vazio."""
    if valor in (None, ""):
        return ""
    if isinstance(valor, (int, float)):
        try:
            return int(valor)
        except Exception:
            return valor
    s = str(valor).strip()
    if not s:
        return ""
    s_num = s.replace(",", ".")
    try:
        n = float(s_num)
        return int(n) if n.is_integer() else n
    except Exception:
        return s


def _status_prioridade_pcf(status):
    s = _normalizar_header(status)
    prioridade = {
        "OPEN": 50,
        "NOT RELEASED": 40,
        "RELEASED WITH COMMENTS": 35,
        "UNDER REVIEW": 30,
        "RELEASED": 20,
        "CLOSED": 10,
        "": 0,
    }
    return prioridade.get(s, 1)


def _valor_num_score(valor):
    v = _intel_num(valor)
    if isinstance(v, (int, float)):
        return float(v)
    try:
        return float(str(v).replace(",", "."))
    except Exception:
        return 0.0


def _melhor_intel_pcf(atual, novo, linha_atual=0, linha_nova=0):
    """
    Escolhe a melhor linha quando a PCF possui mais de uma ocorrência de inteligência.
    Critério:
      1) maior prioridade de status operacional;
      2) maior Open Comments;
      3) maior Qtd Comentários;
      4) maior Under Review;
      5) última linha encontrada.
    """
    if not atual:
        return novo, linha_nova

    score_atual = (
        _status_prioridade_pcf(atual.get("status_final", "")),
        _valor_num_score(atual.get("open_comments", "")),
        _valor_num_score(atual.get("qtd_comentarios", "")),
        _valor_num_score(atual.get("under_review", "")),
        linha_atual,
    )
    score_novo = (
        _status_prioridade_pcf(novo.get("status_final", "")),
        _valor_num_score(novo.get("open_comments", "")),
        _valor_num_score(novo.get("qtd_comentarios", "")),
        _valor_num_score(novo.get("under_review", "")),
        linha_nova,
    )

    if score_novo >= score_atual:
        return novo, linha_nova

    return atual, linha_atual


def _cell_value_openpyxl(ws, row, col):
    try:
        return ws.cell(row=row, column=col).value
    except Exception:
        return None


def _achar_header_pcf_openpyxl(ws):
    """
    Localiza a linha/colunas da inteligência dentro da própria PCF.
    Procura pelos cabeçalhos em qualquer aba, nas primeiras linhas.
    """
    aliases = {
        "qtd_comentarios": {
            "QTD COMENTARIOS", "QTD COMENTARIO", "QTDE COMENTARIOS",
            "QTD COMMENTS", "COMMENTS QTY", "NB PENDING COMMENTS", "PENDING COMMENTS",
        },
        "open_comments": {
            "OPEN COMMENTS", "OPEN COMMENT", "OPEN COMMER", "OPEN COMMENTS QTY",
        },
        "under_review": {
            "UNDER REVIEW", "UNDER REVIE", "UNDER REVIEWS",
        },
        "status_final": {
            "STATUS FINAL PCF", "STATUS FINAL", "FINAL STATUS", "PCF FINAL STATUS",
        },
    }

    max_row_scan = min(ws.max_row or 1, 30)
    max_col_scan = min(ws.max_column or 1, 120)

    melhor = None
    melhor_qtd = 0

    for row in range(1, max_row_scan + 1):
        encontrados = {}
        for col in range(1, max_col_scan + 1):
            h = _normalizar_header(_cell_value_openpyxl(ws, row, col))
            if not h:
                continue

            for campo, nomes in aliases.items():
                if h in nomes and campo not in encontrados:
                    encontrados[campo] = col

        qtd = len(encontrados)
        if qtd > melhor_qtd:
            melhor_qtd = qtd
            melhor = (row, encontrados)

        if qtd >= 3:
            return row, encontrados

    return melhor if melhor_qtd else (None, {})



def _pcf_primeira_aba_util(wb_pcf):
    """Mesma regra da Timeline PCFs: usa a primeira aba visível da PCF."""
    try:
        for ws in wb_pcf.worksheets:
            if getattr(ws, "sheet_state", "visible") == "visible":
                return ws
        return wb_pcf.worksheets[0]
    except Exception:
        return None


def _pcf_data_documental_arquivo(caminho_pcf):
    """
    Retorna a data oficial do cabeçalho da PCF.

    Procura o rótulo exato "Date" na área superior e lê o primeiro valor
    preenchido à direita. Retorna None para permitir fallback ao timestamp do
    arquivo somente quando a data documental não existir ou o arquivo falhar.
    """
    wb_pcf = None
    try:
        wb_pcf = load_workbook(caminho_pcf, read_only=False, data_only=True)
        ws = _pcf_primeira_aba_util(wb_pcf)
        if ws is None:
            return None

        max_row = min(ws.max_row or 0, 20)
        max_col = min(ws.max_column or 0, 40)
        for r in range(1, max_row + 1):
            for c in range(1, max_col + 1):
                if _normalizar_header(ws.cell(r, c).value) != "DATE":
                    continue
                for offset in (2, 1, 3, 4):
                    target_col = c + offset
                    if target_col > (ws.max_column or 0):
                        continue
                    data = _coerce_to_date(ws.cell(r, target_col).value)
                    if data is not None:
                        return data
        return None
    except Exception:
        return None
    finally:
        if wb_pcf is not None:
            try:
                wb_pcf.close()
            except Exception:
                pass


def _pcf_status_final_timeline(ws):
    """
    Regra idêntica à Timeline PCFs:
    STATUS FINAL = último valor preenchido na coluna E, começando em E9.
    """
    status_final = ""
    if ws is None:
        return status_final

    for row in range(9, (ws.max_row or 0) + 1):
        v = ws.cell(row=row, column=5).value  # coluna E
        texto = _valor_intel(v)
        if str(texto).strip():
            status_final = texto

    return status_final


def _pcf_saldos_historico(ws):
    """
    Lê os saldos vigentes de OPEN e UNDER REVIEW no quadro PCF History.

    O detalhe da PCF pode manter comentarios antigos com o texto OPEN mesmo
    depois de tachados. Por isso, o quadro historico e a fonte prioritaria
    para o saldo atual. Retorna None quando o quadro nao puder ser identificado,
    permitindo usar a contagem detalhada como fallback.
    """
    if ws is None:
        return None, None

    max_row = ws.max_row or 0
    max_col = min(ws.max_column or 0, 40)
    history_row = None

    for r in range(1, min(max_row, 60) + 1):
        for c in range(1, max_col + 1):
            if _normalizar_header(ws.cell(r, c).value) == "PCF HISTORY":
                history_row = r
                break
        if history_row:
            break

    if not history_row:
        return None, None

    round_col = None
    open_comments_col = None
    header_end_row = min(max_row, history_row + 8)

    for r in range(history_row + 1, header_end_row + 1):
        for c in range(1, max_col + 1):
            header = _normalizar_header(ws.cell(r, c).value)
            if header == "ROUND" and round_col is None:
                round_col = c
            elif header in {"OPEN COMMENTS", "OPEN COMMENT"}:
                open_comments_col = c

    if round_col is None or open_comments_col is None:
        return None, None

    ultimo_open = None
    ultimo_under_review = None
    data_start_row = header_end_row + 1

    # Cabecalhos mesclados podem terminar antes de history_row + 8. Localiza
    # a primeira rodada real e, a partir dela, considera somente linhas que
    # tenham identificador de rodada (a), b), c), ...).
    for r in range(history_row + 1, min(max_row, history_row + 30) + 1):
        rodada = str(ws.cell(r, round_col).value or "").strip()
        if rodada:
            data_start_row = r
            break

    linhas_sem_rodada = 0
    for r in range(data_start_row, min(max_row, data_start_row + 30) + 1):
        rodada = str(ws.cell(r, round_col).value or "").strip()
        if not rodada:
            linhas_sem_rodada += 1
            if linhas_sem_rodada >= 3:
                break
            continue

        linhas_sem_rodada = 0
        valor_bruto = ws.cell(r, open_comments_col).value
        if valor_bruto in (None, ""):
            continue

        valor = _intel_num(valor_bruto)
        if isinstance(valor, (int, float)):
            ultimo_open = int(valor)
            ultimo_under_review = None
            continue

        texto = _normalizar_header(valor_bruto)
        match_open = re.search(r"(\d+)\s*OPEN\b", texto)
        match_under = re.search(
            r"(\d+)\s*UNDER(?:\s+|[_-])(?:REVIEW|REVISION)\b",
            texto,
        )
        if match_open or match_under:
            ultimo_open = int(match_open.group(1)) if match_open else 0
            ultimo_under_review = int(match_under.group(1)) if match_under else 0

    return ultimo_open, ultimo_under_review


def _pcf_open_comments_historico(ws):
    """Compatibilidade: retorna somente o saldo vigente de comentários OPEN."""
    open_comments, _ = _pcf_saldos_historico(ws)
    return open_comments


def _pcf_qtd_e_open_comments_timeline(ws):
    """
    Regra idêntica à Timeline PCFs:
    - localiza a coluna cujo cabeçalho é Comment Status;
    - conta linhas com Comment Status preenchido;
    - OPEN soma Open Comments;
    - UNDER REVIEW aceita variações operacionais.
    """
    if ws is None:
        return "", "", ""

    comment_status_col = None
    header_row = None

    for r in range(1, min(ws.max_row or 1, 60) + 1):
        for c in range(1, min(ws.max_column or 1, 30) + 1):
            if _normalizar_header(ws.cell(r, c).value) == "COMMENT STATUS":
                comment_status_col = c
                header_row = r
                break
        if comment_status_col:
            break

    open_count = 0
    under_review_count = 0
    total_comments = 0

    under_review_aliases = {
        "UNDER REVIEW",
        "UNDER_REVIEW",
        "UNDER-REVIEW",
        "UNDER  REVIEW",
        "UNDER REVISION",
        "UNDER_REVISION",
        "UNDER-REVISION",
    }

    if comment_status_col:
        for r in range(header_row + 1, (ws.max_row or header_row) + 1):
            status = _normalizar_header(ws.cell(r, comment_status_col).value)

            if not status:
                continue

            total_comments += 1

            if status == "OPEN":
                open_count += 1
            elif status in under_review_aliases:
                under_review_count += 1

    open_historico, under_review_historico = _pcf_saldos_historico(ws)
    if open_historico is not None:
        open_count = open_historico
    if under_review_historico is not None:
        under_review_count = under_review_historico

    return total_comments, open_count, under_review_count


def ler_pcf_intelligence_arquivo(caminho_pcf, cache=None):
    """
    Lê a inteligência operacional diretamente da própria PCF usando a mesma regra
    da Timeline PCFs.

    Regra:
      qtd_comentarios = total de linhas com Comment Status preenchido
      open_comments   = quantidade de Comment Status = OPEN
      under_review    = quantidade de Comment Status = UNDER REVIEW
      status_final    = último valor preenchido na coluna E, a partir de E9

    Na LD PROJETO BASICO:
      Z  = status_final
      AG = status_final
    """
    caminho = normalizar_endereco_hyperlink(caminho_pcf)

    if cache is not None and caminho in cache:
        return cache[caminho]

    vazio = {
        "qtd_comentarios": "",
        "open_comments": "",
        "under_review": "",
        "status_final": "",
    }

    if not caminho or not os.path.exists(caminho):
        if cache is not None:
            cache[caminho] = vazio
        return vazio

    try:
        # Igual à Timeline PCFs: read_only=False para evitar falhas silenciosas
        # em algumas PCFs com estrutura/mesclas/formatação especial.
        wb_pcf = load_workbook(caminho, read_only=False, data_only=True)
    except Exception as exc:
        log(f"⚠️ Não foi possível abrir PCF para ler comentários/status final: {caminho} | {exc}")
        if cache is not None:
            cache[caminho] = vazio
        return vazio

    try:
        ws_pcf = _pcf_primeira_aba_util(wb_pcf)
        qtd_comentarios, open_comments, under_review = _pcf_qtd_e_open_comments_timeline(ws_pcf)
        status_final = _pcf_status_final_timeline(ws_pcf)

        resultado = {
            "qtd_comentarios": _valor_intel(qtd_comentarios),
            "open_comments": _valor_intel(open_comments),
            "under_review": _valor_intel(under_review),
            "status_final": _valor_intel(status_final),
        }

        if cache is not None:
            cache[caminho] = resultado

        return resultado

    except Exception as exc:
        log(f"⚠️ Falha lendo inteligência da PCF pela regra Timeline: {caminho} | {exc}")
        if cache is not None:
            cache[caminho] = vazio
        return vazio

    finally:
        try:
            wb_pcf.close()
        except Exception:
            pass


def carregar_status_pcfs_timeline(app):
    """
    Carrega da Timeline PCFs:
      Aba: PCFs Recebidas TP
      Chave exata: coluna B (PCF LINK)
      Valor retornado: coluna L (STATUS FINAL)

    Esse índice será usado para preencher LD!N.
    A coluna M da LD permanece sendo a data de recebimento da PCF.
    """
    idx = {}

    if not os.path.exists(TIMELINE_PCF):
        log(f"⚠️ Timeline PCFs não encontrada: {TIMELINE_PCF}")
        return idx

    wb_tl = None
    try:
        wb_tl = app.books.open(TIMELINE_PCF, update_links=False, read_only=True)
        ws_tl = wb_tl.sheets["PCFs Recebidas TP"]

        last = ws_tl.range("B" + str(ws_tl.cells.last_cell.row)).end("up").row

        duplicadas = 0
        vazias = 0

        for rr in range(2, last + 1):
            chave = normalizar_chave_pcf(ws_tl[f"B{rr}"].value)
            status = ws_tl[f"L{rr}"].value

            if not chave:
                vazias += 1
                continue

            if chave in idx:
                duplicadas += 1

            idx[chave] = status

        log(f"📘 Status Final PCFs carregados da Timeline: {len(idx)} chaves exatas.")
        if duplicadas:
            log(f"⚠️ Timeline possui {duplicadas} chave(s) duplicada(s) na coluna B; valeu a última ocorrência.")
        if vazias:
            log(f"ℹ️ Timeline possui {vazias} linha(s) sem PCF LINK na coluna B.")

        return idx

    except Exception as e:
        log(f"⚠️ Não foi possível carregar Status Final da Timeline PCFs: {e}")
        return idx

    finally:
        if wb_tl is not None:
            try:
                wb_tl.close()
            except Exception:
                pass


def status_final_da_pcf(status_pcfs, pcf_nome_coluna_l):
    """
    PROCV exato:
      procura LD coluna L exatamente na Timeline coluna B
      retorna Timeline coluna L
    """
    chave = normalizar_chave_pcf(pcf_nome_coluna_l)
    return status_pcfs.get(chave, "")


# ==========================================================
# INSERIR REVISÕES NOVAS (ENGENHARIA) + LOG
# ==========================================================
def inserir_revisoes_novas(ws, idx_eng):
    last = ws.range("B" + str(ws.cells.last_cell.row)).end("up").row

    rev_rows = {}
    all_rows = {}

    for r in range(2, last + 1):
        codigo = normalizar_codigo(ws[f"B{r}"].value)
        if not codigo:
            continue
        rev = normalizar_rev(ws[f"C{r}"].value)
        rev_rows.setdefault(codigo, {})[rev] = r
        all_rows.setdefault(codigo, []).append(r)

    codigos_ordenados = sorted(all_rows.keys(), key=lambda c: max(all_rows[c]), reverse=True)

    total_inseridas = 0
    inseridas_map = {}

    for codigo in codigos_ordenados:
        eng_revs = set(idx_eng.get(codigo, {}).keys())
        if not eng_revs:
            continue

        sheet_revs = set(rev_rows.get(codigo, {}).keys())
        faltantes = sorted(list(eng_revs - sheet_revs), key=rev_key)
        if not faltantes:
            continue

        base_map = rev_rows[codigo]
        if "0" in base_map:
            base_row = base_map["0"]
        else:
            menor_rev = sorted(sheet_revs, key=rev_key)[0]
            base_row = base_map[menor_rev]

        insert_at = max(all_rows[codigo]) + 1

        for new_rev in faltantes:
            ws.api.Rows(base_row).Copy()
            ws.api.Rows(insert_at).Insert()

            ws[f"C{insert_at}"].value = new_rev

            ws.range(f"H{insert_at}:Q{insert_at}").value = None
            for col in ["B", "J", "L", "O", "Q"]:
                limpar_hyperlink(ws[f"{col}{insert_at}"])

            total_inseridas += 1
            inseridas_map.setdefault(codigo, []).append(new_rev)

            rev_rows[codigo][new_rev] = insert_at
            all_rows[codigo].append(insert_at)
            insert_at += 1

    try:
        ws.book.app.api.CutCopyMode = False
    except Exception:
        pass

    if total_inseridas:
        log(f"➕ Revisões novas inseridas na planilha ({ws.name}): {total_inseridas}")
        for codigo, revs in sorted(inseridas_map.items()):
            log(f"   - {codigo}: inseriu revisões {', '.join(revs)}")
    else:
        log(f"ℹ️ Nenhuma revisão nova para inserir (Engenharia x Planilha) na aba {ws.name}.")

    return inseridas_map, total_inseridas

# ==========================================================
# FORMATAÇÃO
# ==========================================================
def _set_cell_text(cell, texto: str):
    """Escreve texto na célula (sem formato de data)."""
    cell.value = texto
    try:
        cell.api.NumberFormat = "@"
    except Exception:
        pass

def aplicar_formatacao(ws, layout=None):
    layout = layout or LAYOUT_LD
    doc_col = _col_layout(layout, "documento") or "B"
    last_row = ws.range(doc_col + str(ws.cells.last_cell.row)).end("up").row
    if last_row < 2:
        return

    # última coluna fixa (Q) para garantir aplicar tudo
    try:
        last_col = ws.range(f"{ULTIMA_COLUNA}1").column
    except Exception:
        last_col = ws.range("A1").end("right").column

    rng_all = ws.range((1, 1), (last_row, last_col))

    # padrão geral
    rng_all.api.Font.Name = "Arial"
    rng_all.api.Font.Size = 11
    rng_all.api.VerticalAlignment = xlCenter
    rng_all.api.HorizontalAlignment = xlCenter

    # alinhamento específico de texto
    ws.range("D:D").api.HorizontalAlignment = xlLeft
    ws.range("E:E").api.HorizontalAlignment = xlLeft
    ws.range("F:F").api.HorizontalAlignment = xlLeft

    # bordas
    for i in range(7, 13):
        rng_all.api.Borders(i).LineStyle = 1
        rng_all.api.Borders(i).Weight = 2

    # cabeçalho
    header = ws.range((1, 1), (1, last_col))
    header.api.Font.Bold = True

    # freeze panes (ou desfazer)
    try:
        ws.api.Activate()
        win = ws.book.app.api.ActiveWindow
        if FREEZE_PANES:
            win.SplitRow = 1
            win.SplitColumn = 0
            win.FreezePanes = True
        else:
            win.FreezePanes = False
            win.SplitRow = 0
            win.SplitColumn = 0
    except Exception:
        pass

    # zebra
    for r in range(2, last_row + 1):
        try:
            if r % 2 == 0:
                ws.range((r, 1), (r, last_col)).api.Interior.Color = 0xF2F2F2
            else:
                ws.range((r, 1), (r, last_col)).api.Interior.Pattern = -4142
        except Exception:
            pass

    # remove formatações condicionais
    try:
        ws.api.Cells.FormatConditions.Delete()
    except Exception:
        pass

    # condicional (H, I, N)
    try:
        col_I = ws.range(f"I2:I{last_row}")
        col_I.api.FormatConditions.Add(Type=1, Operator=3, Formula1='="Emitido"').Interior.Color = 0xC6EFCE
        col_I.api.FormatConditions.Add(Type=1, Operator=3, Formula1='="Não Emitido"').Interior.Color = 0xFCE4D6

        col_H = ws.range(f"H2:H{last_row}")
        col_H.api.FormatConditions.Add(Type=1, Operator=3, Formula1='="Recebido"').Interior.Color = 0xC6EFCE
        col_H.api.FormatConditions.Add(Type=1, Operator=3, Formula1='="Não Recebido"').Interior.Color = 0xFCE4D6

        # N agora é STATUS FINAL da Timeline PCFs.
        # Não aplicar regra antiga "Recebida/Não Recebida", para não conflitar com valores como NOT RELEASED.
    except Exception:
        pass

    # ✅ Forçar formato de DATA (K, M, P) -> dd/mm/aaaa (PT-BR)
    forcar_numberformat_coluna(ws, "K", 2, last_row)
    forcar_numberformat_coluna(ws, "M", 2, last_row)
    forcar_numberformat_coluna(ws, "P", 2, last_row)

    # ✅ Colunas pedidas: Arial 11 + centralizado + alinhado no meio
    for col in ["B", "J", "O", "P", "Q"]:
        try:
            rng = ws.range(f"{col}2:{col}{last_row}")
            rng.api.Font.Name = "Arial"
            rng.api.Font.Size = 11
            rng.api.HorizontalAlignment = xlCenter
            rng.api.VerticalAlignment = xlCenter
        except Exception:
            pass

# ==========================================================
# MEDIÇÃO (copiar aba -> MEDIÇÃO)
# ==========================================================
def extrair_disciplina(codigo: str) -> str:
    if not codigo:
        return ""
    s = str(codigo).upper()
    m = re.search(r"I-([A-Z0-9]{2})", s)
    return m.group(1) if m else ""

def _flatten(col):
    if isinstance(col, list) and col and isinstance(col[0], list):
        return [linha[0] for linha in col]
    elif isinstance(col, list):
        return col
    else:
        return [col]

def atualizar_medicao(wb, aba_origem):
    ws_origem = wb.sheets[aba_origem]
    try:
        ws_destino = wb.sheets[ABA_MEDICAO]
    except Exception:
        ws_destino = wb.sheets.add(ABA_MEDICAO)
        log(f"🆕 Aba '{ABA_MEDICAO}' não existia e foi criada.")

    last_row_origem = ws_origem.range("B" + str(ws_origem.cells.last_cell.row)).end("up").row
    if last_row_origem < 2:
        log(f"⚠️ Aba '{aba_origem}' sem linhas para copiar para MEDIÇÃO.")
        return

    faixa_codigos = ws_origem.range(f"B2:B{last_row_origem}")
    faixa_revs    = ws_origem.range(f"C2:C{last_row_origem}")
    faixa_titulos = ws_origem.range(f"D2:D{last_row_origem}")
    faixa_disc_f  = ws_origem.range(f"F2:F{last_row_origem}")
    faixa_status  = ws_origem.range(f"I2:I{last_row_origem}")
    faixa_data    = ws_origem.range(f"Z2:Z{last_row_origem}")

    codigos_flat = _flatten(faixa_codigos.value)
    revs_flat    = _flatten(faixa_revs.value)
    titulos_flat = _flatten(faixa_titulos.value)
    disc_f_flat  = _flatten(faixa_disc_f.value)
    status_flat  = _flatten(faixa_status.value)
    datas_flat   = _flatten(faixa_data.value)

    n = min(len(codigos_flat), len(revs_flat), len(titulos_flat), len(disc_f_flat), len(status_flat), len(datas_flat))
    codigos_flat = codigos_flat[:n]
    revs_flat    = revs_flat[:n]
    titulos_flat = titulos_flat[:n]
    disc_f_flat  = disc_f_flat[:n]
    status_flat  = status_flat[:n]
    datas_flat   = datas_flat[:n]

    best_por_codigo = {}
    unicos_codigos = []
    disciplinas_A  = []
    titulos_unicos = []
    disciplinas_F  = []
    status_unicos  = []
    datas_unicas   = []

    for cod, rev, tit, disc, stat, dt in zip(codigos_flat, revs_flat, titulos_flat, disc_f_flat, status_flat, datas_flat):
        if cod in (None, ""):
            continue
        cod_str = str(cod).strip()
        if not cod_str:
            continue

        rev_ord = rev_key(normalizar_rev(rev))
        dt_coer = _coerce_to_date(dt)
        dt_ord = dt_coer or date.min

        atual = best_por_codigo.get(cod_str)
        if atual is None or (rev_ord > atual["rev_ord"]) or (rev_ord == atual["rev_ord"] and dt_ord > atual["dt_ord"]):
            best_por_codigo[cod_str] = {
                "rev_ord": rev_ord,
                "dt_ord": dt_ord,
                "titulo": tit,
                "disc": disc,
                "status": stat,
                "data": dt_coer,
            }

    for cod_str, info in best_por_codigo.items():
        unicos_codigos.append(cod_str)
        disciplinas_A.append(extrair_disciplina(cod_str))
        titulos_unicos.append(info["titulo"])
        disciplinas_F.append(info["disc"])
        status_unicos.append(info["status"])
        datas_unicas.append(info["data"])

    first_dest_row = 4
    max_last_row = 577
    max_qtd = max_last_row - first_dest_row + 1

    qtd_total = len(unicos_codigos)
    if qtd_total == 0:
        log("⚠️ Nenhum código encontrado para copiar para MEDIÇÃO.")
        return

    qtd_linhas = min(qtd_total, max_qtd)
    unicos_codigos = unicos_codigos[:qtd_linhas]
    disciplinas_A  = disciplinas_A[:qtd_linhas]
    titulos_unicos = titulos_unicos[:qtd_linhas]
    disciplinas_F  = disciplinas_F[:qtd_linhas]
    status_unicos  = status_unicos[:qtd_linhas]
    datas_unicas   = datas_unicas[:qtd_linhas]

    last_dest_row = first_dest_row + qtd_linhas - 1

    ws_destino.range("A4:F577").clear_contents()

    ws_destino.range(f"A{first_dest_row}:A{last_dest_row}").value = [[d] for d in disciplinas_A]
    ws_destino.range(f"B{first_dest_row}:B{last_dest_row}").value = [[c] for c in unicos_codigos]
    ws_destino.range(f"C{first_dest_row}:C{last_dest_row}").value = [[t] for t in titulos_unicos]
    ws_destino.range(f"D{first_dest_row}:D{last_dest_row}").value = [[df] for df in disciplinas_F]
    ws_destino.range(f"E{first_dest_row}:E{last_dest_row}").value = [[s] for s in status_unicos]
    ws_destino.range(f"F{first_dest_row}:F{last_dest_row}").value = [[dt] for dt in datas_unicas]

    # ✅ força formato de data na MEDIÇÃO (coluna F) -> dd/mm/aaaa
    forcar_numberformat_coluna(ws_destino, "F", first_dest_row, last_dest_row)

    log(f"✅ {qtd_linhas} linhas copiadas para '{ABA_MEDICAO}' a partir de '{aba_origem}': A4:F{last_dest_row}.")

# ==========================================================
# PROCESSAR UMA ABA (LD / LD MARENOVA)
# ==========================================================
def _preencher_data_por_modo(cell, modo: str, dt: datetime | None, obs: str):
    m = (modo or "DATA").upper().strip()
    if m == "MANTER":
        return
    if m == "OBS":
        _set_cell_text(cell, obs)
        return
    # DATA
    setar_data(cell, dt)

def processar_aba(wb, aba_nome, idx_eng, idx_eng_codigos, idx_grd, idx_pcf, idx_pcf_resp, idx_grd_resp, status_pcfs, inserir_revisoes=True, pcf_intel_cache=None, layout=None):
    ws = wb.sheets[aba_nome]
    layout = _layout_para_aba(aba_nome, layout)

    if pcf_intel_cache is None:
        pcf_intel_cache = {}

    log(f"📄 Processando aba: {aba_nome}")

    doc_col = _col_layout(layout, "documento")
    rev_col = _col_layout(layout, "revisao")
    status_col = _col_layout(layout, "status")
    status_grd_col = _col_layout(layout, "status_grd")
    data_km_col = _col_layout(layout, "data_recebimento_km")

    _af_state = capturar_autofiltro(ws)
    remover_autofiltro(ws)

    try:
        # Inserção de revisões novas só é segura no layout da LD principal.
        if inserir_revisoes and aba_nome == ABA_LD:
            inserir_revisoes_novas(ws, idx_eng)
        elif inserir_revisoes:
            log(f"ℹ️ Inserção de revisões novas ignorada para {aba_nome}: layout diferente da LD principal.")
        else:
            log(f"ℹ️ Inserção de revisões novas desativada para a aba {aba_nome}. Atualizando apenas linhas existentes.")

        last = ws.range(f"{doc_col}" + str(ws.cells.last_cell.row)).end("up").row

        STATUS_H_BLOQUEADOS = {
            "APROVADO",
            "APROVADO COM COMENTÁRIOS",
            "APROVADO COM COMENTARIOS",
            "NÃO APROVADO",
            "NAO APROVADO",
            "CANCELAR",
            "CANCELADO",
            "PARA INFORMAÇÃO",
            "PARA INFORMACAO",
            "PARA CONSTRUÇÃO",
            "PARA CONSTRUCAO",
        }

        STATUS_H_PRESERVAR_BASICO = {
            "REPROVADO",
            "APROVADO",
            "APROVADO COM COMENTÁRIOS",
            "APROVADO COM COMENTARIOS",
            "APROVADO SEM COMENTÁRIOS",
            "APROVADO SEM COMENTARIOS",
            "AGUARDANDO PCF",
        }

        STATUS_AUTO_ATUALIZAVEIS = {
            "NÃO RECEBIDO",
            "NAO RECEBIDO",
            "RECEBIDO",
            "RECEBIDO E NÃO EMITIDO",
            "RECEBIDO E NAO EMITIDO",
            "AGUARDANDO PCF",
        }

        for r in range(last, 1, -1):
            codigo_exibido = str(_valor_layout(ws, layout, "documento", r) or "").strip()
            codigo = normalizar_codigo(codigo_exibido)
            rev = normalizar_rev(_valor_layout(ws, layout, "revisao", r))
            pcf_anterior = str(_valor_layout(ws, layout, "pcf", r) or "").strip()
            revisao_atualizada = False

            if not codigo:
                continue

            eh_projeto_basico = aba_nome == ABA_LD_BASICO

            # Projeto básico: mantém o comportamento de "última revisão existente"
            # sem inserir novas linhas.
            if eh_projeto_basico:
                revs_eng = list(idx_eng.get(codigo, {}).keys())
                if revs_eng:
                    maior_rev = sorted(revs_eng, key=rev_key)[-1]
                    if rev_key(maior_rev) > rev_key(rev):
                        _set_layout(ws, layout, "revisao", r, maior_rev)
                        rev = maior_rev
                        revisao_atualizada = True
                        log(f"🔄 {aba_nome} L{r} | {codigo}: revisão atualizada para {maior_rev}")

            status_h = str(_valor_layout(ws, layout, "status", r) or "").strip().upper()
            if revisao_atualizada and pcf_anterior and status_h != "CANCELADO":
                _set_layout(ws, layout, "status", r, "Aguardando PCF")
                if LOG_DETALHADO:
                    log(
                        f"   [{status_col}] {aba_nome} L{r}: nova revisão emitida; "
                        f"{status_h or '-'} -> Aguardando PCF"
                    )
                status_h = "AGUARDANDO PCF"
            preservar_status_basico = eh_projeto_basico and status_h in STATUS_H_PRESERVAR_BASICO

            # O hyperlink do documento sempre deve abrir a pasta, inclusive em
            # linhas cujo status bloqueia as demais atualizações operacionais.
            info_eng = idx_eng.get(codigo, {}).get(rev)
            if info_eng:
                link_ok = _setar_hyperlink_layout(
                    ws, layout, "documento", r, info_eng["path"], codigo_exibido or codigo
                )
                if LOG_DETALHADO:
                    resultado_link = "criado" if link_ok else "FALHOU"
                    log(
                        f"   [DOC] {aba_nome} L{r} | {codigo}_R{rev} => "
                        f"hyperlink de pasta {resultado_link} | pasta={info_eng['path']}"
                    )
            else:
                # Se a indexação não reencontrar o documento, converte um
                # hyperlink antigo de arquivo para a pasta que o contém.
                cell_documento = _cell_layout(ws, layout, "documento", r)
                link_anterior = _sync_obter_hyperlink(cell_documento) if cell_documento is not None else ""
                endereco_anterior = normalizar_endereco_hyperlink(link_anterior)
                extensao_anterior = os.path.splitext(endereco_anterior)[1].lower()
                if endereco_anterior and extensao_anterior in EXTENSOES:
                    pasta_anterior = os.path.dirname(endereco_anterior)
                    link_ok = _setar_hyperlink_layout(
                        ws, layout, "documento", r, pasta_anterior, codigo_exibido or codigo
                    )
                    if LOG_DETALHADO:
                        resultado_link = "convertido" if link_ok else "FALHOU"
                        log(
                            f"   [DOC] {aba_nome} L{r} | {codigo}_R{rev} => "
                            f"hyperlink antigo {resultado_link} para pasta={pasta_anterior}"
                        )
                else:
                    _set_layout(ws, layout, "documento", r, codigo_exibido or codigo)
                if LOG_DETALHADO:
                    if not endereco_anterior:
                        log(
                            f"   [DOC] {aba_nome} L{r} | {codigo}_R{rev} => "
                            "não localizado e sem hyperlink anterior"
                        )

            if not eh_projeto_basico and status_h in STATUS_H_BLOQUEADOS:
                if LOG_DETALHADO:
                    log(f"   [SKIP] {aba_nome} L{r} ignorada ({status_col} = {status_h})")
                continue

            documento_encontrado = codigo in idx_eng_codigos
            pcf_recebida_para_rev = False

            if documento_encontrado:
                mapa_pcf_status = idx_pcf.get(codigo, {})
                base_rev_status = (rev or "").strip().upper()

                for rev_pcf_status in mapa_pcf_status.keys():
                    ok_status, _sufixo_status = _split_by_base(rev_pcf_status, base_rev_status)
                    if ok_status:
                        pcf_recebida_para_rev = True
                        break

            # Regra de recebimento KM. No Projeto Básico a data oficial é K.
            valor_data_recebimento_km = _valor_layout(ws, layout, "data_recebimento_km", r)
            tem_data_recebimento_km = bool(
                _coerce_to_date(valor_data_recebimento_km)
                or str(valor_data_recebimento_km or "").strip()
            )

            not_applicable_com_recebimento = (
                eh_projeto_basico
                and "NOT APPLICABLE" in str(codigo or "").upper()
                and tem_data_recebimento_km
            )

            status_auto = (
                "Recebido"
                if documento_encontrado and pcf_recebida_para_rev
                else "Aguardando PCF"
                if documento_encontrado and not pcf_recebida_para_rev
                else "Recebido e não Emitido"
                if tem_data_recebimento_km
                else "Não Recebido"
            )

            if not_applicable_com_recebimento:
                _set_layout(ws, layout, "status", r, "Recebido e não Emitido")
                if LOG_DETALHADO:
                    log(f"   [{status_col}/{status_grd_col}] {aba_nome} L{r}: NOT APPLICABLE com data KM preenchida.")
            elif eh_projeto_basico:
                if status_h in STATUS_AUTO_ATUALIZAVEIS:
                    _set_layout(ws, layout, "status", r, status_auto)
                    if LOG_DETALHADO:
                        log(f"   [{status_col}] {aba_nome} L{r}: {status_h or '-'} -> {status_auto}")
                elif preservar_status_basico:
                    if LOG_DETALHADO:
                        log(f"   [{status_col}] {aba_nome} L{r} preservada ({status_col} = {status_h}); atualizando demais colunas.")
                else:
                    if not status_h:
                        _set_layout(ws, layout, "status", r, status_auto)
            else:
                _set_layout(ws, layout, "status", r, status_auto)

            # GRD de emissão.
            info = idx_grd.get(codigo, {}).get(rev)
            if info:
                _set_layout(ws, layout, "status_grd", r, "Emitido")
                _setar_hyperlink_layout(ws, layout, "grd", r, info["path"], info["grd"])

                cell_data_grd = _cell_layout(ws, layout, "data_grd", r)
                if cell_data_grd is not None:
                    _preencher_data_por_modo(cell_data_grd, COL_K_MODO, info.get("date"), OBS_COL_K)
                    if (COL_K_MODO or "").upper().strip() == "DATA":
                        _aplicar_formato_data(cell_data_grd)

                if LOG_DETALHADO:
                    log(f"   [GRD {status_grd_col}] {aba_nome} L{r} | {codigo}_R{rev} => GRD={info['grd']} | link={info['path']} | data={_fmt_dt(info.get('date'))}")
            else:
                _set_layout(ws, layout, "status_grd", r, "Não Emitido")
                _set_layout(ws, layout, "grd", r, None)

                cell_data_grd = _cell_layout(ws, layout, "data_grd", r)
                if cell_data_grd is not None and (COL_K_MODO or "").upper() != "MANTER":
                    cell_data_grd.value = None

                _limpar_hyperlink_layout(ws, layout, "grd", r)

                if LOG_DETALHADO:
                    log(f"   [GRD {status_grd_col}] {aba_nome} L{r} | {codigo}_R{rev} => GRD NÃO encontrado")

            if not_applicable_com_recebimento:
                _set_layout(ws, layout, "status_grd", r, "NOT APPLICABLE")

            # PCF recebida.
            info_pcf = None
            mapa = idx_pcf.get(codigo, {})
            rev_doc = normalizar_rev(_valor_layout(ws, layout, "revisao", r))
            best = None
            best_key = None

            if mapa and rev_doc:
                base = (rev_doc or "").strip().upper()
                for rev_pcf, cand in mapa.items():
                    ok, sufixo = _split_by_base(rev_pcf, base)
                    if not ok:
                        continue

                    k = (_suffix_key(sufixo), cand.get("date") or datetime.min)
                    if (best_key is None) or (k[0] > best_key[0]) or (k[0] == best_key[0] and k[1] > best_key[1]):
                        best_key = k
                        best = cand

            info_pcf = best

            if info_pcf:
                _setar_hyperlink_layout(ws, layout, "pcf", r, info_pcf["path"], info_pcf["pcf"])

                cell_data_pcf = _cell_layout(ws, layout, "data_pcf", r)
                if cell_data_pcf is not None:
                    _preencher_data_por_modo(cell_data_pcf, COL_M_MODO, info_pcf.get("date"), OBS_COL_M)
                    if (COL_M_MODO or "").upper().strip() == "DATA":
                        _aplicar_formato_data(cell_data_pcf)

                pcf_coluna = _valor_layout(ws, layout, "pcf", r)
                intel_pcf = ler_pcf_intelligence_arquivo(info_pcf.get("path"), pcf_intel_cache)

                status_final = _valor_intel(intel_pcf.get("status_final", ""))
                if not str(status_final).strip():
                    status_final = status_final_da_pcf(status_pcfs, pcf_coluna)

                _set_layout(ws, layout, "status_pcf", r, status_final)

                if _col_layout(layout, "qtd_comentarios"):
                    _set_layout(ws, layout, "qtd_comentarios", r, intel_pcf.get("qtd_comentarios", ""))
                if _col_layout(layout, "open_comments"):
                    _set_layout(ws, layout, "open_comments", r, intel_pcf.get("open_comments", ""))
                if _col_layout(layout, "under_review"):
                    _set_layout(ws, layout, "under_review", r, intel_pcf.get("under_review", ""))
                if _col_layout(layout, "status_final_pcf"):
                    _set_layout(ws, layout, "status_final_pcf", r, status_final or intel_pcf.get("status_final", ""))

                if LOG_DETALHADO:
                    log(
                        f"   [PCF DIRETO] {aba_nome} L{r} | {codigo}_R{rev_doc} "
                        f"=> PCF='{pcf_coluna}' | STATUS='{status_final}' "
                        f"| QTD='{intel_pcf.get('qtd_comentarios', '')}' "
                        f"| OPEN='{intel_pcf.get('open_comments', '')}' "
                        f"| UNDER='{intel_pcf.get('under_review', '')}'"
                    )
            else:
                revisoes_disponiveis = sorted(mapa.keys(), key=rev_key) if mapa else []
                # Excluir o hyperlink antes do valor. O Excel pode restaurar o
                # TextToDisplay antigo quando Hyperlinks.Delete vem depois.
                _limpar_hyperlink_layout(ws, layout, "pcf", r)
                _set_layout(ws, layout, "pcf", r, None)

                cell_data_pcf = _cell_layout(ws, layout, "data_pcf", r)
                if cell_data_pcf is not None and (COL_M_MODO or "").upper() != "MANTER":
                    cell_data_pcf.value = None

                _set_layout(ws, layout, "status_pcf", r, None)

                for campo in ("qtd_comentarios", "open_comments", "under_review", "status_final_pcf"):
                    if _col_layout(layout, campo):
                        _set_layout(ws, layout, campo, r, None)

                status_atual_sem_pcf = str(
                    _valor_layout(ws, layout, "status", r) or ""
                ).strip().upper()
                if (
                    eh_projeto_basico
                    and revisoes_disponiveis
                    and status_atual_sem_pcf != "CANCELADO"
                ):
                    _set_layout(ws, layout, "status", r, "Aguardando PCF")
                    if LOG_DETALHADO:
                        log(
                            f"   [{status_col}] {aba_nome} L{r}: PCF apenas de outra revisão; "
                            f"{status_atual_sem_pcf or '-'} -> Aguardando PCF"
                        )

                if LOG_DETALHADO:
                    if revisoes_disponiveis:
                        log(
                            f"   [PCF OUTRA REVISÃO IGNORADA] {aba_nome} L{r} | "
                            f"{codigo}_R{rev_doc} | disponíveis={','.join(revisoes_disponiveis)}"
                        )
                    else:
                        log(f"   [PCF AGUARDANDO] {aba_nome} L{r} | {codigo}_R{rev} => PCF não encontrada")

            # Resposta de PCF.
            mapa_resp = idx_pcf_resp.get(codigo, {})
            rev_doc_resp = normalizar_rev(_valor_layout(ws, layout, "revisao", r))
            rev_recebida = (info_pcf or {}).get("rev", "")
            rev_resposta_esperada = _pcf_resposta_da_recebida(rev_recebida, rev_doc_resp)
            info_resp = mapa_resp.get(rev_resposta_esperada) if rev_resposta_esperada else None

            # Uma resposta anterior ao recebimento nao pertence ao ciclo atual.
            if info_resp and info_pcf:
                dt_recebida = info_pcf.get("date")
                dt_resposta = info_resp.get("date")
                if dt_recebida and dt_resposta and dt_resposta < dt_recebida:
                    if LOG_DETALHADO:
                        log(
                            f"   [PCF RESP CRONOLOGIA INVALIDA] {aba_nome} L{r} | "
                            f"recebida={rev_recebida} em {_fmt_dt(dt_recebida)} | "
                            f"resposta={rev_resposta_esperada} em {_fmt_dt(dt_resposta)}"
                        )
                    info_resp = None

            if info_resp:
                _setar_hyperlink_layout(ws, layout, "pcf_resposta", r, info_resp["path"], info_resp["pcf"])

                cell_data_resp = _cell_layout(ws, layout, "data_resposta", r)
                if cell_data_resp is not None:
                    _preencher_data_por_modo(cell_data_resp, COL_P_MODO, info_resp.get("date"), OBS_COL_P)
                    if (COL_P_MODO or "").upper().strip() == "DATA":
                        _aplicar_formato_data(cell_data_resp)

                grd_resp = idx_grd_resp.get(info_resp["pcf"].upper(), "")
                if grd_resp:
                    _setar_hyperlink_layout(ws, layout, "grd_resposta", r, os.path.join(PASTA_GRD, grd_resp), grd_resp)
                else:
                    _limpar_hyperlink_layout(ws, layout, "grd_resposta", r)
                    _set_layout(ws, layout, "grd_resposta", r, None)

                if LOG_DETALHADO:
                    log(
                        f"   [PCF RESP PAREADA] {aba_nome} L{r} | "
                        f"recebida={rev_recebida} => resposta={rev_resposta_esperada} | "
                        f"PCF_RESP={info_resp['pcf']} | GRD={grd_resp or '-'}"
                    )
            else:
                revisoes_resp_disponiveis = sorted(mapa_resp.keys(), key=rev_key) if mapa_resp else []
                # Mesma protecao contra restauracao do texto do hyperlink.
                _limpar_hyperlink_layout(ws, layout, "pcf_resposta", r)
                _limpar_hyperlink_layout(ws, layout, "grd_resposta", r)
                _set_layout(ws, layout, "pcf_resposta", r, None)

                cell_data_resp = _cell_layout(ws, layout, "data_resposta", r)
                if cell_data_resp is not None and (COL_P_MODO or "").upper() != "MANTER":
                    cell_data_resp.value = None

                _set_layout(ws, layout, "grd_resposta", r, None)

                if LOG_DETALHADO:
                    if revisoes_resp_disponiveis:
                        log(
                            f"   [PCF RESP OUTRA REVISÃO IGNORADA] {aba_nome} L{r} | "
                            f"{codigo}_R{rev_doc_resp} | disponíveis={','.join(revisoes_resp_disponiveis)}"
                        )
                    else:
                        log(
                            f"   [PCF RESP AGUARDANDO] {aba_nome} L{r} | "
                            f"{codigo}_R{rev} => resposta não encontrada"
                        )

        if APLICAR_FORMATACAO:
            aplicar_formatacao(ws, layout)
    finally:
        restaurar_autofiltro(ws, _af_state)
        garantir_autofiltro(ws)

def _sync_obter_hyperlink(cell):
    """Obtém hyperlink de uma célula xlwings sem interromper a atualização."""
    try:
        hls = cell.api.Hyperlinks
        if hls.Count >= 1:
            h = hls.Item(1)
            endereco = str(h.Address or "").strip()
            sub = str(h.SubAddress or "").strip()
            if endereco and sub:
                return f"{endereco}#{sub}"
            return endereco or sub
    except Exception:
        pass
    return ""


def validar_revisoes_pcfs_workbook(wb, abas_layouts):
    """Repara respostas históricas e bloqueia somente PCF recebida de outra base."""
    divergencias = []
    reparos = 0

    def limpar_resposta(ws, layout, linha, motivo):
        nonlocal reparos
        for campo in ("pcf_resposta", "grd_resposta"):
            if _col_layout(layout, campo):
                _limpar_hyperlink_layout(ws, layout, campo, linha)
                _set_layout(ws, layout, campo, linha, None)
        if _col_layout(layout, "data_resposta"):
            _set_layout(ws, layout, "data_resposta", linha, None)
        reparos += 1
        log(f"🧹 [PCF RESPOSTA HISTÓRICA REMOVIDA] {ws.name} L{linha} | {motivo}")

    for aba_nome, layout in abas_layouts:
        try:
            ws = wb.sheets[aba_nome]
        except Exception:
            continue

        doc_col = _col_layout(layout, "documento")
        rev_col = _col_layout(layout, "revisao")
        if not doc_col or not rev_col:
            continue

        last = ws.range(doc_col + str(ws.cells.last_cell.row)).end("up").row
        for r in range(2, last + 1):
            documento = normalizar_codigo(ws[f"{doc_col}{r}"].value)
            revisao = normalizar_rev(ws[f"{rev_col}{r}"].value)
            if not documento or not revisao:
                continue

            for campo, rotulo in (("pcf", "PCF Nº"), ("pcf_resposta", "PCF RESPONDIDA")):
                coluna = _col_layout(layout, campo)
                if not coluna:
                    continue
                valor = ws[f"{coluna}{r}"].value
                if not str(valor or "").strip():
                    continue

                revisao_pcf = _revisao_pcf_do_nome(valor)
                compativel, _ = _split_by_base(revisao_pcf, revisao)
                if not compativel:
                    if campo == "pcf_resposta":
                        limpar_resposta(
                            ws, layout, r,
                            f"resposta={revisao_pcf or '?'} incompatível com documento R{revisao}",
                        )
                        continue
                    divergencias.append(
                        f"{aba_nome} L{r} | {documento}_R{revisao} | "
                        f"{rotulo}='{valor}' (revisão PCF={revisao_pcf or '?'})"
                    )

    # Segunda camada: recebida e respondida precisam pertencer ao mesmo ciclo.
    for aba_nome, layout in abas_layouts:
        try:
            ws = wb.sheets[aba_nome]
        except Exception:
            continue

        doc_col = _col_layout(layout, "documento")
        rev_col = _col_layout(layout, "revisao")
        col_pcf = _col_layout(layout, "pcf")
        col_resp = _col_layout(layout, "pcf_resposta")
        if not doc_col or not rev_col or not col_pcf or not col_resp:
            continue

        last = ws.range(doc_col + str(ws.cells.last_cell.row)).end("up").row
        for r in range(2, last + 1):
            revisao = normalizar_rev(ws[f"{rev_col}{r}"].value)
            valor_pcf = ws[f"{col_pcf}{r}"].value
            valor_resp = ws[f"{col_resp}{r}"].value
            rev_recebida = _revisao_pcf_do_nome(valor_pcf)
            rev_respondida = _revisao_pcf_do_nome(valor_resp)
            esperada = _pcf_resposta_da_recebida(rev_recebida, revisao)

            if rev_respondida and rev_respondida != esperada:
                limpar_resposta(
                    ws, layout, r,
                    f"ciclo inválido: recebida=R{rev_recebida}, "
                    f"respondida=R{rev_respondida}, esperada=R{esperada or '?'}",
                )
                continue

            col_data_pcf = _col_layout(layout, "data_pcf")
            col_data_resp = _col_layout(layout, "data_resposta")
            if valor_resp and col_data_pcf and col_data_resp:
                data_pcf = ws[f"{col_data_pcf}{r}"].value
                data_resp = ws[f"{col_data_resp}{r}"].value
                if (
                    isinstance(data_pcf, datetime)
                    and isinstance(data_resp, datetime)
                    and data_resp < data_pcf
                ):
                    limpar_resposta(
                        ws, layout, r,
                        f"cronologia inválida: resposta {_fmt_dt(data_resp)} "
                        f"anterior ao recebimento {_fmt_dt(data_pcf)}",
                    )

    if divergencias:
        for item in divergencias[:50]:
            log(f"🚨 [PCF REVISÃO INCOMPATÍVEL] {item}")
        raise RuntimeError(
            f"Validação PCF bloqueou o salvamento: {len(divergencias)} vínculo(s) "
            "de PCF recebida/respondida pertencem a outra revisão."
        )

    log(
        "✅ Validação PCF concluída: nenhuma PCF recebida vinculada a revisão "
        f"incompatível; respostas históricas removidas={reparos}."
    )
    return reparos


def _status_documento_por_status_pcf(valor):
    """Converte o status final da PCF no status operacional da LD Projeto Básico."""
    status = re.sub(r"\s+", " ", str(valor or "").strip().upper())
    mapa = {
        "NOT RELEASED": "Reprovado",
        "RELEASED": "Aprovado sem Comentários",
        "RELEASED WITH COMMENTS": "Aprovado com comentários",
    }
    return mapa.get(status, "")


def atualizar_status_documento_por_pcf_ld_basico(wb):
    """Atualiza M usando AH como fonte prioritária e AA como fallback."""
    try:
        ws = wb.sheets[ABA_LD_BASICO]
    except Exception as exc:
        log(f"⚠️ Status por PCF não atualizado: {exc}")
        return 0

    layout = LAYOUT_PROJETO_BASICO
    doc_col = _col_layout(layout, "documento")
    last = ws.range(doc_col + str(ws.cells.last_cell.row)).end("up").row
    atualizados = 0
    contagem = {}

    for r in range(2, last + 1):
        if not normalizar_codigo(_valor_layout(ws, layout, "documento", r)):
            continue

        status_ah = _valor_layout(ws, layout, "status_final_pcf", r)
        status_aa = _valor_layout(ws, layout, "status_pcf", r)
        novo_status = (
            _status_documento_por_status_pcf(status_ah)
            or _status_documento_por_status_pcf(status_aa)
        )
        if not novo_status:
            continue

        status_atual = str(_valor_layout(ws, layout, "status", r) or "").strip()
        if status_atual != novo_status:
            _set_layout(ws, layout, "status", r, novo_status)
            atualizados += 1
        contagem[novo_status] = contagem.get(novo_status, 0) + 1

    resumo = ", ".join(f"{status}={qtd}" for status, qtd in sorted(contagem.items())) or "nenhum status reconhecido"
    log(f"✅ {ABA_LD_BASICO}: status M atualizado pela PCF (AH prioritária; AA fallback): {resumo}.")
    return atualizados


def sincronizar_pcf_intelligence_ld_basico(wb):
    """
    Sincroniza a PCF Intelligence da aba LD para a aba LD PROJETO BASICO.

    A aba LD principal mantém o layout original e já possui a leitura direta das
    PCFs consolidada. A aba LD PROJETO BASICO tem novo layout, então copiamos
    por chave Documento + Revisão apenas:
      PCF / Data PCF / Status PCF / Qtd / Open / Under / Status Final
    sem alterar status de documento, GRD, KM ou demais campos operacionais.
    """
    try:
        ws_ld = wb.sheets[ABA_LD]
        ws_basico = wb.sheets[ABA_LD_BASICO]
    except Exception as exc:
        log(f"ℹ️ Sincronização PCF {ABA_LD_BASICO} ignorada: {exc}")
        return 0

    layout_ld = LAYOUT_LD
    layout_basico = LAYOUT_PROJETO_BASICO

    try:
        last_ld = ws_ld.range(_col_layout(layout_ld, "documento") + str(ws_ld.cells.last_cell.row)).end("up").row
        last_basico = ws_basico.range(_col_layout(layout_basico, "documento") + str(ws_basico.cells.last_cell.row)).end("up").row
    except Exception as exc:
        log(f"⚠️ Não foi possível localizar linhas para sincronizar PCF {ABA_LD_BASICO}: {exc}")
        return 0

    if last_ld < 2 or last_basico < 2:
        return 0

    idx_exato = {}

    for r in range(2, last_ld + 1):
        documento = normalizar_codigo(_valor_layout(ws_ld, layout_ld, "documento", r))
        revisao = normalizar_rev(_valor_layout(ws_ld, layout_ld, "revisao", r))

        if not documento:
            continue

        dados = {
            "pcf": _valor_layout(ws_ld, layout_ld, "pcf", r),
            "data_pcf": _valor_layout(ws_ld, layout_ld, "data_pcf", r),
            "status_final": _valor_layout(ws_ld, layout_ld, "status_pcf", r),
            "qtd": _valor_layout(ws_ld, layout_ld, "qtd_comentarios", r),
            "open": _valor_layout(ws_ld, layout_ld, "open_comments", r),
            "under": _valor_layout(ws_ld, layout_ld, "under_review", r),
            "status_ay": _valor_layout(ws_ld, layout_ld, "status_final_pcf", r),
            "pcf_link": _sync_obter_hyperlink(_cell_layout(ws_ld, layout_ld, "pcf", r)),
            "rev": revisao,
        }

        if not any(str(dados.get(campo) or "").strip() for campo in ("pcf", "status_final", "qtd", "open", "under", "status_ay")):
            continue

        idx_exato[(documento, revisao)] = dados

    sincronizadas = 0

    for r in range(2, last_basico + 1):
        documento = normalizar_codigo(_valor_layout(ws_basico, layout_basico, "documento", r))
        revisao = normalizar_rev(_valor_layout(ws_basico, layout_basico, "revisao", r))

        if not documento:
            continue

        # Correspondência estrita: nunca reutiliza PCF de outra revisão do documento.
        dados = idx_exato.get((documento, revisao))
        if not dados:
            continue

        if dados.get("pcf"):
            link = normalizar_endereco_hyperlink(dados.get("pcf_link", ""))
            if link:
                _setar_hyperlink_layout(ws_basico, layout_basico, "pcf", r, link, dados.get("pcf"))
            else:
                _set_layout(ws_basico, layout_basico, "pcf", r, dados.get("pcf"))

        _set_layout(ws_basico, layout_basico, "data_pcf", r, dados.get("data_pcf"))
        cell_data = _cell_layout(ws_basico, layout_basico, "data_pcf", r)
        if dados.get("data_pcf") and cell_data is not None:
            try:
                _aplicar_formato_data(cell_data)
            except Exception:
                pass

        status_pcf_sync = dados.get("status_final")
        _set_layout(ws_basico, layout_basico, "status_pcf", r, status_pcf_sync)
        _set_layout(ws_basico, layout_basico, "qtd_comentarios", r, dados.get("qtd"))
        _set_layout(ws_basico, layout_basico, "open_comments", r, dados.get("open"))
        _set_layout(ws_basico, layout_basico, "under_review", r, dados.get("under"))
        _set_layout(ws_basico, layout_basico, "status_final_pcf", r, status_pcf_sync)

        sincronizadas += 1

    if sincronizadas:
        log(f"🔁 {ABA_LD_BASICO}: PCF Intelligence sincronizada da aba LD em {sincronizadas} linha(s).")
    else:
        log(f"ℹ️ {ABA_LD_BASICO}: nenhuma PCF Intelligence encontrada para sincronizar da aba LD.")

    return sincronizadas

# ==========================================================
# LD BASICO x GENERAL LIST KM (preencher AN)
# ==========================================================
def _texto_excel_seguro(valor):
    """Converte valores do Excel para texto limpo, sem perder códigos numéricos."""
    if valor is None:
        return ""

    if isinstance(valor, datetime):
        return valor.strftime("%d/%m/%Y")

    if isinstance(valor, date):
        return valor.strftime("%d/%m/%Y")

    if isinstance(valor, float):
        return str(int(valor)) if valor.is_integer() else str(valor).strip()

    if isinstance(valor, int):
        return str(valor)

    return str(valor).replace("\xa0", " ").strip()


def _normalizar_chave_documento(valor):
    """
    Normaliza Nº Transpetro para comparação segura entre abas.

    Mantém o código original para exibição, mas remove espaços invisíveis,
    quebras de linha e diferenças de maiúsculas/minúsculas.
    """
    texto = _texto_excel_seguro(valor).upper()
    texto = texto.replace("\n", "").replace("\r", "").replace("\t", "")
    texto = texto.replace("\xa0", " ")
    texto = re.sub(r"\s+", "", texto)
    return texto.strip()


def _adicionar_unico(lista, valor):
    """Adiciona um valor textual em uma lista preservando ordem e evitando duplicidade."""
    texto = _texto_excel_seguro(valor)
    if texto and texto not in lista:
        lista.append(texto)


def indexar_general_list_km(wb):
    """
    Cria índice da aba GENERAL LIST KM usando o Nº Transpetro como chave.

    Regras oficiais:
      chave = GENERAL LIST KM coluna F (Customer Document Num / Nº Transpetro)
      H     = GENERAL LIST KM coluna C (Number / Nº Documento KM)
      I     = GENERAL LIST KM coluna D (Title / KM Title)
      J     = GENERAL LIST KM coluna O (Transmittal Number)
      K     = GENERAL LIST KM coluna P (Data recebimento KM)

    Nova regra LD PROJETO BASICO:
      quando houver mais de um KM para o mesmo Nº Transpetro, NÃO agrupa com " / ".
      A rotina mantém um registro por ocorrência para que a LD PROJETO BASICO possa
      repetir a linha inteira e preencher H:K individualmente.
    """
    idx = {}

    try:
        ws = wb.sheets[ABA_GENERAL_LIST_KM]
    except Exception as exc:
        log(f"⚠️ Aba '{ABA_GENERAL_LIST_KM}' não encontrada. Colunas H:K da LD PROJETO BASICO não serão atualizadas: {exc}")
        return idx

    try:
        # A coluna F é a chave oficial (Customer Document Num / Nº Transpetro).
        last = ws.range("F" + str(ws.cells.last_cell.row)).end("up").row
    except Exception as exc:
        log(f"⚠️ Não foi possível localizar última linha da aba '{ABA_GENERAL_LIST_KM}': {exc}")
        return idx

    if last < 2:
        log(f"ℹ️ Aba '{ABA_GENERAL_LIST_KM}' sem dados para indexar.")
        return idx

    valores_km = _flatten(ws.range(f"C2:C{last}").value)
    valores_title = _flatten(ws.range(f"D2:D{last}").value)
    valores_tp = _flatten(ws.range(f"F2:F{last}").value)
    valores_transmittal = _flatten(ws.range(f"O2:O{last}").value)
    valores_data_km = _flatten(ws.range(f"P2:P{last}").value)

    total_linhas = min(
        len(valores_km),
        len(valores_title),
        len(valores_tp),
        len(valores_transmittal),
        len(valores_data_km),
    )

    duplicados_identicos_ignorados = 0

    for numero_km, title_km, numero_tp, transmittal, data_km in zip(
        valores_km[:total_linhas],
        valores_title[:total_linhas],
        valores_tp[:total_linhas],
        valores_transmittal[:total_linhas],
        valores_data_km[:total_linhas],
    ):
        chave_tp = _normalizar_chave_documento(numero_tp)
        if not chave_tp:
            continue

        registro = {
            "numero": _texto_excel_seguro(numero_km),
            "titulo": _texto_excel_seguro(title_km),
            "transmittal": _texto_excel_seguro(transmittal),
            # Mantém data como valor tipado para o Excel não inverter dia/mês.
            "data": _coerce_to_date(data_km) or _texto_excel_seguro(data_km),
        }

        # Ignora linhas totalmente vazias da GENERAL LIST.
        if not any(str(registro.get(campo) or "").strip() for campo in ("numero", "titulo", "transmittal", "data")):
            continue

        item = idx.setdefault(chave_tp, {
            "records": [],
            # Mantém listas antigas apenas para compatibilidade/debug.
            "numbers": [],
            "titles": [],
            "transmittals": [],
            "datas": [],
        })

        assinatura = (
            registro["numero"],
            registro["titulo"],
            registro["transmittal"],
            registro["data"],
        )

        assinaturas_existentes = {
            (
                r.get("numero", ""),
                r.get("titulo", ""),
                r.get("transmittal", ""),
                r.get("data", ""),
            )
            for r in item["records"]
        }

        if assinatura in assinaturas_existentes:
            duplicados_identicos_ignorados += 1
            continue

        item["records"].append(registro)
        _adicionar_unico(item["numbers"], registro["numero"])
        _adicionar_unico(item["titles"], registro["titulo"])
        _adicionar_unico(item["transmittals"], registro["transmittal"])
        _adicionar_unico(item["datas"], registro["data"])

    total_vinculos = sum(len(item.get("records", [])) for item in idx.values())
    log(
        f"🔎 GENERAL LIST KM indexada: {len(idx)} Nº Transpetro com {total_vinculos} vínculo(s) KM "
        f"({duplicados_identicos_ignorados} vínculo(s) idêntico(s) ignorado(s))."
    )
    return idx


def _linhas_contiguas_por_chave_ld_basico(ws, doc_col, last):
    """Agrupa linhas contíguas da LD PROJETO BASICO pela chave da coluna C."""
    blocos = []
    r = 2

    while r <= last:
        chave = _normalizar_chave_documento(ws[f"{doc_col}{r}"].value)
        inicio = r

        while r + 1 <= last and _normalizar_chave_documento(ws[f"{doc_col}{r + 1}"].value) == chave:
            r += 1

        fim = r
        if chave:
            blocos.append((inicio, fim, chave))

        r += 1

    return blocos


def _copiar_linha_excel(ws, linha_origem, linha_destino):
    """Insere uma linha nova e copia integralmente valores/formatação da linha origem."""
    ws.api.Rows(linha_origem).Copy()
    ws.api.Rows(linha_destino).Insert()
    try:
        ws.book.app.api.CutCopyMode = False
    except Exception:
        pass


def preencher_numero_km_ld_basico(wb, idx_general_km=None):
    """
    Preenche a LD PROJETO BASICO com dados da GENERAL LIST KM.

    Regras:
      LD PROJETO BASICO coluna C == GENERAL LIST KM coluna F
      H = GENERAL LIST KM coluna C (Number / Nº Documento KM)
      I = GENERAL LIST KM coluna D (Title / KM Title)
      J = GENERAL LIST KM coluna O (Transmittal Number)
      K = GENERAL LIST KM coluna P (Data Recebimento KM)

    Sincroniza preservando os ajustes cadastrais existentes:
      - Não apaga nem altera H:J de linhas já preenchidas.
      - Regrava K pela data oficial da GENERAL LIST KM quando o Nº KM coincide.
      - Usa H (Nº Documento KM) como chave do vínculo.
      - Preenche somente linhas com H:K totalmente vazias.
      - Insere uma nova linha quando não houver linha vazia disponível.
      - Registra divergências no log para conferência manual.
    """
    if idx_general_km is None:
        idx_general_km = indexar_general_list_km(wb)

    if not idx_general_km:
        log(f"ℹ️ {ABA_LD_BASICO} H:K não atualizadas: índice GENERAL LIST KM vazio.")
        return 0

    try:
        ws = wb.sheets[ABA_LD_BASICO]
    except Exception as exc:
        log(f"⚠️ Aba '{ABA_LD_BASICO}' não encontrada. H:K não serão atualizadas: {exc}")
        return 0

    layout = LAYOUT_PROJETO_BASICO
    doc_col = _col_layout(layout, "documento")

    try:
        last = ws.range(f"{doc_col}" + str(ws.cells.last_cell.row)).end("up").row
    except Exception as exc:
        log(f"⚠️ Não foi possível localizar última linha da aba '{ABA_LD_BASICO}': {exc}")
        return 0

    if last < 2:
        return 0

    blocos = _linhas_contiguas_por_chave_ld_basico(ws, doc_col, last)

    # Trava de segurança contra GENERAL LIST parcialmente carregada. Compara os
    # números KM já existentes na LD com os números disponíveis na fonte. Se a
    # cobertura cair muito, não sincroniza H:K; as demais partes da atualização
    # podem continuar normalmente e o log informa a causa.
    numeros_fonte_globais = {
        _normalizar_chave_documento(registro.get("numero", ""))
        for item in idx_general_km.values()
        for registro in item.get("records", [])
        if _normalizar_chave_documento(registro.get("numero", ""))
    }
    numeros_ld_existentes = set()
    for rr in range(2, last + 1):
        numero_ld = _texto_excel_seguro(ws[f"H{rr}"].value)
        chave_numero_ld = _normalizar_chave_documento(numero_ld)
        if chave_numero_ld and chave_numero_ld not in {"N/A", "NA", "CANCELADO"}:
            numeros_ld_existentes.add(chave_numero_ld)

    if len(numeros_ld_existentes) >= 20:
        encontrados = numeros_ld_existentes & numeros_fonte_globais
        cobertura = len(encontrados) / len(numeros_ld_existentes)
        if cobertura < 0.75:
            log(
                f"🚨 [KM NÃO SINCRONIZADO] GENERAL LIST KM aparentemente incompleta: "
                f"somente {len(encontrados)}/{len(numeros_ld_existentes)} números KM existentes "
                f"na LD foram encontrados na fonte ({cobertura:.1%}). H:K foram integralmente "
                "preservadas; verifique os vínculos/consultas externas da planilha."
            )
            return 0

    preenchidas = 0
    linhas_inseridas = 0
    sem_vinculo = 0
    preservadas = 0
    datas_corrigidas = 0
    avisos = 0

    # Processa de baixo para cima para não deslocar blocos ainda pendentes.
    for inicio, fim, chave_tp in reversed(blocos):
        dados = idx_general_km.get(chave_tp, {})
        registros = list(dados.get("records", [])) if dados else []

        def ler_hk(rr):
            valores = ws.range(f"H{rr}:K{rr}").value
            if isinstance(valores, list) and len(valores) == 1 and isinstance(valores[0], list):
                valores = valores[0]
            elif not isinstance(valores, list):
                valores = [valores]
            return tuple(_texto_excel_seguro(v) for v in valores)

        if not registros:
            sem_vinculo += 1
            existentes = [ler_hk(rr) for rr in range(inicio, fim + 1)]
            if any(any(linha) for linha in existentes):
                preservadas += sum(1 for linha in existentes if any(linha))
                log(
                    f"⚠️ [KM PRESERVADO] {chave_tp} | linhas {inicio}:{fim} possuem H:K manual, "
                    "mas não há correspondência na GENERAL LIST KM. Nenhum valor foi alterado."
                )
                avisos += 1
            continue

        fim_atual = fim

        def escrever_registro(rr, registro):
            ws.range(f"H{rr}:J{rr}").value = [[
                registro.get("numero", ""),
                registro.get("titulo", ""),
                registro.get("transmittal", ""),
            ]]
            valor_data = registro.get("data", "")
            if valor_data:
                setar_data(ws[f"K{rr}"], valor_data)
            else:
                ws[f"K{rr}"].value = None

        for registro in registros:
            numero_fonte = _texto_excel_seguro(registro.get("numero", ""))
            chave_numero_fonte = _normalizar_chave_documento(numero_fonte)

            if not chave_numero_fonte:
                log(
                    f"⚠️ [KM IGNORADO] {chave_tp} | registro da GENERAL LIST KM sem Nº Documento KM: "
                    f"{registro}. Nenhuma linha foi alterada."
                )
                avisos += 1
                continue

            linhas_mesmo_numero = []
            linhas_vazias = []
            for rr in range(inicio, fim_atual + 1):
                atual = ler_hk(rr)
                if not any(atual):
                    linhas_vazias.append(rr)
                elif _normalizar_chave_documento(atual[0]) == chave_numero_fonte:
                    linhas_mesmo_numero.append((rr, atual))

            if linhas_mesmo_numero:
                rr, atual = linhas_mesmo_numero[0]
                esperado = (
                    numero_fonte,
                    _texto_excel_seguro(registro.get("titulo", "")),
                    _texto_excel_seguro(registro.get("transmittal", "")),
                    _texto_excel_seguro(registro.get("data", "")),
                )

                # H:J podem conter ajustes manuais e continuam preservadas. K,
                # porém, tem como fonte oficial GENERAL LIST KM!P e precisa ser
                # regravada inclusive nas linhas já existentes. Isso também
                # corrige datas antigas que o Excel interpretou como mm/dd.
                valor_data_fonte = registro.get("data", "")
                data_fonte = _coerce_to_date(valor_data_fonte)
                data_ld_antes = _coerce_to_date(ws[f"K{rr}"].value)
                if data_fonte is not None:
                    setar_data(ws[f"K{rr}"], data_fonte)
                    if data_ld_antes != data_fonte:
                        datas_corrigidas += 1
                        log(
                            f"📅 [DATA KM CORRIGIDA] {chave_tp} | linha {rr} | "
                            f"{_texto_excel_seguro(data_ld_antes)} -> "
                            f"{_texto_excel_seguro(data_fonte)}"
                        )

                if atual[:3] != esperado[:3]:
                    log(
                        f"⚠️ [KM DIVERGENTE] {chave_tp} | linha {rr} | "
                        f"LD H:J={atual[:3]} | GENERAL LIST H:J={esperado[:3]}. "
                        "Valores H:J da LD preservados; K sincronizada pela fonte oficial."
                    )
                    avisos += 1
                else:
                    preservadas += 1
                if len(linhas_mesmo_numero) > 1:
                    duplicadas = ", ".join(str(item[0]) for item in linhas_mesmo_numero)
                    log(
                        f"⚠️ [KM DUPLICADO] {chave_tp} | Nº KM {numero_fonte} aparece nas linhas "
                        f"{duplicadas}. Nenhuma duplicidade foi removida."
                    )
                    avisos += 1
                continue

            if linhas_vazias:
                destino = linhas_vazias[0]
            else:
                destino = fim_atual + 1
                _copiar_linha_excel(ws, inicio, destino)
                ws.range(f"H{destino}:K{destino}").clear_contents()
                fim_atual = destino
                linhas_inseridas += 1

            escrever_registro(destino, registro)
            preenchidas += 1

        numeros_fonte = {
            _normalizar_chave_documento(registro.get("numero", ""))
            for registro in registros
            if _normalizar_chave_documento(registro.get("numero", ""))
        }
        for rr in range(inicio, fim_atual + 1):
            atual = ler_hk(rr)
            chave_numero_atual = _normalizar_chave_documento(atual[0])
            if any(atual) and chave_numero_atual not in numeros_fonte:
                log(
                    f"⚠️ [KM MANUAL] {chave_tp} | linha {rr} | H:K={atual} não consta na "
                    "GENERAL LIST KM. Registro manual preservado."
                )
                preservadas += 1
                avisos += 1

    try:
        destino_last = ws.range(f"{doc_col}" + str(ws.cells.last_cell.row)).end("up").row
        destino = ws.range(f"H2:J{destino_last}")
        destino.api.NumberFormat = "@"
        destino.api.Font.Name = "Arial"
        destino.api.Font.Size = 11
        destino.api.HorizontalAlignment = xlCenter
        destino.api.VerticalAlignment = xlCenter
        destino.api.WrapText = True
        datas = ws.range(f"K2:K{destino_last}")
        datas.api.NumberFormatLocal = DATE_NUMBERFORMAT_LOCAL
        datas.api.Font.Name = "Arial"
        datas.api.Font.Size = 11
        datas.api.HorizontalAlignment = xlCenter
        datas.api.VerticalAlignment = xlCenter
    except Exception:
        pass

    log(
        f"✅ {ABA_LD_BASICO} H:K sincronizadas sem sobrescrever: "
        f"{preenchidas} novo(s) vínculo(s), {linhas_inseridas} linha(s) inserida(s), "
        f"{datas_corrigidas} data(s) existente(s) corrigida(s), "
        f"{preservadas} registro(s) existente(s) preservado(s), "
        f"{sem_vinculo} chave(s) sem fonte e {avisos} aviso(s) para conferência."
    )
    return preenchidas

# ==========================================================
# PROCESSAMENTO
# ==========================================================


# ==========================================================
# IMPORTAÇÃO DA LD PARA O BANCO DO GED
# ==========================================================
def _valor_celula(cell):
    v = cell.value
    if v is None:
        return ""
    try:
        if isinstance(v, datetime):
            return v.strftime("%d/%m/%Y")
        if isinstance(v, date):
            return v.strftime("%d/%m/%Y")
    except Exception:
        pass
    return str(v).strip()


def _hyperlink_celula(cell):
    try:
        hls = cell.api.Hyperlinks
        if hls.Count >= 1:
            h = hls.Item(1)
            endereco = str(h.Address or "").strip()
            sub = str(h.SubAddress or "").strip()
            if endereco and sub:
                return f"{endereco}#{sub}"
            return endereco or sub
    except Exception:
        pass
    return ""


def _normalizar_header_importacao(valor):
    """Normaliza cabeçalhos da LD para busca segura de colunas na importação."""
    texto = str(valor or "").strip().upper()
    if not texto:
        return ""
    texto = (
        texto.replace("º", "")
        .replace("°", "")
        .replace("ª", "")
        .replace("Á", "A")
        .replace("À", "A")
        .replace("Â", "A")
        .replace("Ã", "A")
        .replace("É", "E")
        .replace("Ê", "E")
        .replace("Í", "I")
        .replace("Ó", "O")
        .replace("Ô", "O")
        .replace("Õ", "O")
        .replace("Ú", "U")
        .replace("Ç", "C")
    )
    return re.sub(r"[^A-Z0-9]+", "", texto)


def _coluna_letra_para_numero(coluna):
    """Converte letra de coluna Excel para índice numérico 1-based."""
    total = 0
    for ch in str(coluna or "").strip().upper():
        if "A" <= ch <= "Z":
            total = total * 26 + (ord(ch) - ord("A") + 1)
    return total or 1


def _resolver_coluna_transmittal_number(ws, fallback="AO"):
    """
    Localiza dinamicamente a coluna Transmittal Number na linha 1.

    Mantém fallback oficial em AO, mas evita coluna vazia quando o cabeçalho
    estiver deslocado na LD/LD BASICO.
    """
    fallback_num = _coluna_letra_para_numero(fallback)

    aliases = {
        "TRANSMITTALNUMBER",
        "TRANSMITTALNUMERO",
        "TRANSMITTALNUM",
        "TRANSMITTALNO",
        "TRANSMITTALN",
    }

    try:
        # Até BD cobre todos os campos operacionais atuais; 100 deixa margem segura.
        for col in range(1, 101):
            header = _normalizar_header_importacao(ws.range((1, col)).value)
            if not header:
                continue

            if header in aliases:
                return col

            if header.startswith("TRANSMITTAL") and any(
                token in header for token in ("NUMBER", "NUMERO", "NUM", "NO", "N")
            ):
                return col

    except Exception:
        pass

    return fallback_num



def importar_aba_ld_banco(ws, origem_aba, layout=None):
    """
    Importa uma aba da LD para o banco do GED usando o layout informado.
    A origem_aba faz parte da identidade do registro.
    """
    layout = _layout_para_aba(origem_aba, layout)

    ultima_linha = ws.used_range.last_cell.row

    origem_texto = str(origem_aba or "").strip()
    origem_upper = origem_texto.upper()

    if "PROJETO" in origem_upper or "BASICO" in origem_upper:
        origem_normalizada = "LD Projeto Basico"
    elif "MARENOVA" in origem_upper:
        origem_normalizada = "LD Marenova Executivo"
    else:
        origem_normalizada = "LD"

    total_linhas = 0
    documentos_exclusivos = set()

    log(
        f"📄 Importando aba {origem_aba} como origem '{origem_normalizada}' "
        f"| used_range até linha {ultima_linha}"
    )

    for r in range(2, ultima_linha + 1):
        documento = _texto_excel_seguro(_valor_layout(ws, layout, "documento", r))
        revisao = _texto_excel_seguro(_valor_layout(ws, layout, "revisao", r))

        if not documento:
            continue

        total_linhas += 1
        documentos_exclusivos.add(documento)

        def valor(campo, fallback=""):
            """Valor seguro para gravar no banco: nunca retorna None."""
            bruto = _valor_layout(ws, layout, campo, r, fallback)
            return _texto_excel_seguro(bruto)

        status_final = valor("status_final_pcf") or valor("status_pcf")

        DocumentoLD.objects.update_or_create(
            origem_aba=origem_normalizada,
            documento=documento,
            revisao=revisao,
            defaults={
                "titulo": valor("titulo"),
                "disciplina": valor("disciplina") or valor("disciplina_alt"),

                "status_documento": valor("status"),
                "status_grd": valor("status_grd"),

                "grd": valor("grd"),
                "data_grd": valor("data_grd"),

                "pcf": valor("pcf"),
                "data_pcf": valor("data_pcf"),
                "status_final_pcf": status_final,

                "pcf_resposta": valor("pcf_resposta"),
                "data_resposta": valor("data_resposta"),
                "grd_resposta": valor("grd_resposta"),

                "numero_interno": valor("numero_interno"),
                "numero_documento_km": valor("numero_documento_km"),
                "transmittal_km": valor("transmittal_km"),
                "data_recebimento_km": valor("data_recebimento_km"),
                "casco": valor("casco"),

                "qtd_comentarios": valor("qtd_comentarios"),
                "open_comments": valor("open_comments"),
                "under_review": valor("under_review"),

                "posted_date": valor("posted_date"),
                "status": valor("status_bv"),
                "since": valor("since_bv"),
                "action": valor("action_bv"),
                "nb_pending_comments": valor("nb_pending_comments"),

                "caminho_documento": _hyperlink_celula(_cell_layout(ws, layout, "documento", r)) or "",
                "caminho_grd": _hyperlink_celula(_cell_layout(ws, layout, "grd", r)) or "",
                "caminho_pcf": _hyperlink_celula(_cell_layout(ws, layout, "pcf", r)) or "",
                "caminho_resposta": _hyperlink_celula(_cell_layout(ws, layout, "pcf_resposta", r)) or "",
                "caminho_grd_resposta": _hyperlink_celula(_cell_layout(ws, layout, "grd_resposta", r)) or "",
            },
        )

    log(f"✅ {origem_normalizada}: {total_linhas} linhas importadas.")
    log(f"✅ {origem_normalizada}: {len(documentos_exclusivos)} documentos exclusivos.")

    return {
        "aba": origem_normalizada,
        "linhas": total_linhas,
        "exclusivos": len(documentos_exclusivos),
        "documentos": documentos_exclusivos,
    }

def importar_ld_banco(wb, wb_marenova=None):
    """
    Importa somente as bases do novo piloto:
      - LD PROJETO BASICO
      - LD MARENOVA P EXECUTIVO
    O Dashboard passa a refletir essas duas origens.
    """
    log("💾 Atualizando banco Django com LD PROJETO BASICO + LD MARENOVA P EXECUTIVO...")

    abas = [
        (wb, ABA_LD_BASICO, LAYOUT_PROJETO_BASICO),
    ]

    if wb_marenova is not None:
        abas.append((wb_marenova, ABA_LD_MARENOVA_EXECUTIVO, LAYOUT_MARENOVA_EXECUTIVO))

    resumo = {}
    total_linhas = 0
    todos_documentos = set()

    # A exclusão e todas as importações formam uma única operação. Qualquer falha
    # restaura automaticamente os registros anteriores.
    with transaction.atomic():
        DocumentoLD.objects.all().delete()

        for workbook, nome_aba, layout in abas:
            resultado = importar_aba_ld_banco(workbook.sheets[nome_aba], nome_aba, layout=layout)
            if resultado["linhas"] <= 0:
                raise RuntimeError(f"A aba {nome_aba} não possui documentos válidos para importar.")

            resumo[nome_aba] = resultado
            total_linhas += resultado["linhas"]
            todos_documentos.update(resultado["documentos"])

    log("✅ Banco Django atualizado.")
    log(f"📊 Total linhas importadas: {total_linhas}")
    log(f"📊 Total documentos exclusivos geral: {len(todos_documentos)}")

    return {
        "abas": resumo,
        "total": total_linhas,
        "exclusivos_geral": len(todos_documentos),
    }

def processar():
    global LOG_FILE
    atualizar_progresso_ld(2, "Preparando atualização LD Projeto Básico...", "running", "Inicializando rotina da nova Atualização LD.")
    os.makedirs(PASTA_LOGS, exist_ok=True)
    os.makedirs(PASTA_BACKUPS, exist_ok=True)
    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    LOG_FILE = os.path.join(PASTA_LOGS, f"LDP_PROJETO_BASICO_{ts}.log")
    log(f"🧾 Log: {LOG_FILE}")

    backup_path = backup_arquivo(PLANILHA)
    backup_marenova_path = None
    if os.path.exists(PLANILHA_MARENOVA_EXECUTIVO):
        backup_marenova_path = backup_arquivo(PLANILHA_MARENOVA_EXECUTIVO)

    atualizar_progresso_ld(8, "Backups criados.", "running", "Backups das planilhas LD criados com segurança.")

    log("🔎 Indexando Engenharia (código + revisão + pasta)...")
    idx_eng = indexar_engenharia_info()
    idx_eng_codigos = set(idx_eng.keys())
    log(f"   - Códigos na Engenharia: {len(idx_eng_codigos)}")
    atualizar_progresso_ld(18, "Engenharia indexada.", "running", f"{len(idx_eng_codigos)} códigos encontrados na Engenharia.")

    log("🔎 Indexando GRDs/PCFs...")
    idx_grd = indexar_grds()
    atualizar_progresso_ld(28, "GRDs indexadas.", "running", "Índice de GRDs concluído.")

    idx_pcf = indexar_pcfs(PASTA_PCF, excluir_subpastas=[PASTA_PCF_RESPOSTA], data_origem=DATA_PCF_ORIGEM)
    atualizar_progresso_ld(38, "PCFs indexadas.", "running", "Índice de PCFs recebidas concluído.")

    idx_pcf_resp = indexar_pcfs(PASTA_PCF_RESPOSTA, data_origem=DATA_PCF_RESP_ORIGEM)
    atualizar_progresso_ld(46, "Respostas PCF indexadas.", "running", "Índice de respostas PCF concluído.")

    idx_grd_resp = indexar_grd_resposta_pcf()

    wb = None
    wb_marenova = None

    try:
        with xw.App(visible=False, add_book=False) as app:
            app.display_alerts = False
            app.screen_updating = False

            status_pcfs = {}
            pcf_intel_cache = {}

            log("ℹ️ Timeline PCFs desativada nesta rotina; status final será lido diretamente das PCFs.")

            atualizar_progresso_ld(52, "Abrindo LD Projeto Básico...", "running", "Abrindo planilha principal do piloto.")
            wb = app.books.open(
                PLANILHA,
                update_links=False,
                read_only=False,
                ignore_read_only_recommended=True,
            )
            if bool(wb.api.ReadOnly):
                raise RuntimeError(
                    "A LD principal foi aberta pelo Excel como somente leitura. "
                    "Feche a planilha em todas as estações e execute novamente."
                )

            # A GENERAL LIST KM possui dados/consultas que podem continuar sendo
            # atualizados em segundo plano após a abertura. Aguarda a conclusão
            # antes de montar qualquer índice, evitando ler uma versão antiga e
            # somente receber os novos vínculos no salvamento final.
            atualizar_progresso_ld(
                55,
                "Atualizando GENERAL LIST KM...",
                "running",
                "Aguardando consultas e cálculos da planilha principal.",
            )
            log("🔄 Atualizando consultas e cálculos da planilha principal...")
            try:
                wb.api.RefreshAll()
                app.api.CalculateUntilAsyncQueriesDone()
                app.api.CalculateFull()
                log("✅ Consultas e cálculos concluídos antes da indexação KM.")
            except Exception as exc:
                raise RuntimeError(
                    f"Não foi possível concluir a atualização da GENERAL LIST KM: {exc}"
                ) from exc

            # A aba LD principal continua sendo processada para manter a base de sincronização
            # da PCF Intelligence, mas o banco importará somente LD PROJETO BASICO.
            atualizar_progresso_ld(62, "Processando aba LD...", "running", "Atualizando LD principal como fonte de sincronização.")
            processar_aba(
                wb,
                ABA_LD,
                idx_eng,
                idx_eng_codigos,
                idx_grd,
                idx_pcf,
                idx_pcf_resp,
                idx_grd_resp,
                status_pcfs,
                inserir_revisoes=True,
                pcf_intel_cache=pcf_intel_cache,
                layout=LAYOUT_LD,
            )

            atualizar_progresso_ld(75, "Processando LD PROJETO BASICO...", "running", "Atualizando novo layout do Projeto Básico.")
            processar_aba(
                wb,
                ABA_LD_BASICO,
                idx_eng,
                idx_eng_codigos,
                idx_grd,
                idx_pcf,
                idx_pcf_resp,
                idx_grd_resp,
                status_pcfs,
                inserir_revisoes=False,
                pcf_intel_cache=pcf_intel_cache,
                layout=LAYOUT_PROJETO_BASICO,
            )

            sincronizar_pcf_intelligence_ld_basico(wb)
            atualizar_status_documento_por_pcf_ld_basico(wb)

            validar_revisoes_pcfs_workbook(wb, [
                (ABA_LD, LAYOUT_LD),
                (ABA_LD_BASICO, LAYOUT_PROJETO_BASICO),
            ])

            atualizar_progresso_ld(82, "Atualizando vínculos KM...", "running", "Preenchendo LD PROJETO BASICO colunas H:K a partir da GENERAL LIST KM.")
            idx_general_km = indexar_general_list_km(wb)
            preencher_numero_km_ld_basico(wb, idx_general_km)

            if os.path.exists(PLANILHA_MARENOVA_EXECUTIVO):
                atualizar_progresso_ld(86, "Abrindo LD Marenova Executivo...", "running", "Abrindo planilha Marenova separada.")
                wb_marenova = app.books.open(
                    PLANILHA_MARENOVA_EXECUTIVO,
                    update_links=False,
                    read_only=False,
                    ignore_read_only_recommended=True,
                )
                if bool(wb_marenova.api.ReadOnly):
                    raise RuntimeError(
                        "A LD Marenova Executivo foi aberta pelo Excel como somente leitura. "
                        "Feche a planilha em todas as estações e execute novamente."
                    )

                atualizar_progresso_ld(88, "Processando LD MARENOVA P EXECUTIVO...", "running", "Atualizando Marenova Executivo no arquivo separado.")
                processar_aba(
                    wb_marenova,
                    ABA_LD_MARENOVA_EXECUTIVO,
                    idx_eng,
                    idx_eng_codigos,
                    idx_grd,
                    idx_pcf,
                    idx_pcf_resp,
                    idx_grd_resp,
                    status_pcfs,
                    inserir_revisoes=False,
                    pcf_intel_cache=pcf_intel_cache,
                    layout=LAYOUT_MARENOVA_EXECUTIVO,
                )
                validar_revisoes_pcfs_workbook(wb_marenova, [
                    (ABA_LD_MARENOVA_EXECUTIVO, LAYOUT_MARENOVA_EXECUTIVO),
                ])
            else:
                log(f"⚠️ Planilha Marenova Executivo não encontrada: {PLANILHA_MARENOVA_EXECUTIVO}")

            atualizar_progresso_ld(92, "Importando bases para o banco...", "running", "Atualizando DocumentoLD com Projeto Básico e Marenova Executivo.")
            log("💾 Importando LD Projeto Básico + Marenova Executivo para banco do GED...")
            resumo_ld = importar_ld_banco(wb, wb_marenova)
            log(f"✅ LD importada para o banco: {resumo_ld.get('total', 0)} registros.")

            atualizar_progresso_ld(97, "Salvando planilhas LD...", "running", "Salvando alterações nas planilhas do piloto.")
            backup_arquivo(PLANILHA)
            if os.path.exists(PLANILHA_MARENOVA_EXECUTIVO):
                backup_arquivo(PLANILHA_MARENOVA_EXECUTIVO)

            log("🔒 Backup de segurança criado antes do salvamento das LDs.")
            wb.save()

            if wb_marenova is not None:
                wb_marenova.save()

            atualizar_progresso_ld(100, "Atualização LD Projeto Básico concluída.", "done", "Atualização LD Projeto Básico finalizada com sucesso.")
            log("✅ LDP Projeto Básico finalizado com sucesso!")

    except Exception as e:
        atualizar_progresso_ld(100, "Erro na Atualização LD Projeto Básico.", "error", f"Erro durante processamento: {e}", erro=str(e))
        log(f"❌ Erro durante processamento: {e}")
        log(f"🧯 Tentando restaurar backup principal: {backup_path}")

        try:
            shutil.copy2(backup_path, PLANILHA)
            log("✅ Backup principal restaurado com sucesso.")
        except Exception as rb_err:
            log(f"❌ Falha ao restaurar backup principal: {rb_err}")

        if backup_marenova_path:
            log(f"🧯 Tentando restaurar backup Marenova: {backup_marenova_path}")
            try:
                shutil.copy2(backup_marenova_path, PLANILHA_MARENOVA_EXECUTIVO)
                log("✅ Backup Marenova restaurado com sucesso.")
            except Exception as rb_err:
                log(f"❌ Falha ao restaurar backup Marenova: {rb_err}")

        raise

    finally:
        for livro in (wb_marenova, wb):
            if livro is not None:
                try:
                    livro.close()
                except Exception:
                    pass

# ==========================================================
# EXECUÇÃO SEGURA VIA GED
# ==========================================================
LOCK_FILE = os.path.join(PASTA_LOGS, "atualizar_ld_projeto_basico.lock")


def _lock_ativo_recente(lock_file: str, horas_limite: int = 6) -> bool:
    """
    Evita duas execuções simultâneas da atualização da LD.
    Se existir um lock antigo, considera travado e libera automaticamente.
    """
    if not os.path.exists(lock_file):
        return False

    try:
        criado_em = datetime.fromtimestamp(os.path.getmtime(lock_file))
        idade = datetime.now() - criado_em

        if idade.total_seconds() > horas_limite * 3600:
            try:
                os.remove(lock_file)
                return False
            except Exception:
                return True

        return True
    except Exception:
        return True


def _criar_lock(lock_file: str):
    os.makedirs(os.path.dirname(lock_file), exist_ok=True)
    with open(lock_file, "w", encoding="utf-8") as f:
        f.write(f"Iniciado em: {datetime.now().strftime('%d/%m/%Y %H:%M:%S')}\n")


def _remover_lock(lock_file: str):
    try:
        if os.path.exists(lock_file):
            os.remove(lock_file)
    except Exception:
        pass


def executar():
    """
    Entry point usado pelo GED/Django.

    Não executa nada no import.
    Mantém a lógica original em processar().
    Protege contra execução simultânea.
    Retorna dicionário padrão para a view exibir messages.
    """
    resetar_progresso_ld()

    if _lock_ativo_recente(LOCK_FILE):
        atualizar_progresso_ld(
            0,
            "Atualização LD bloqueada.",
            "blocked",
            "Atualização LD já está em execução ou ficou travada com lock recente.",
        )
        return {
            "ok": False,
            "status": "cancelado",
            "mensagem": (
                "Atualização LD já está em execução ou ficou travada com lock recente. "
                "Aguarde finalizar antes de executar novamente."
            ),
            "detalhes": {"lock_file": LOCK_FILE},
        }

    _criar_lock(LOCK_FILE)

    try:
        print("🚀 Atualização LD Projeto Básico iniciada pelo GED")
        atualizar_progresso_ld(1, "Atualização LD iniciada.", "running", "Execução iniciada pelo GED.")
        processar()

        return {
            "ok": True,
            "mensagem": "Atualização LD Projeto Básico executada com sucesso.",
            "detalhes": {
                "planilha": PLANILHA,
                "planilha_marenova": PLANILHA_MARENOVA_EXECUTIVO,
                "aba_ld": ABA_LD,
                "aba_ld_projeto_basico": ABA_LD_BASICO,
                "aba_ld_marenova_executivo": ABA_LD_MARENOVA_EXECUTIVO,
                "logs": PASTA_LOGS,
            },
        }

    except Exception as e:
        print(f"❌ Erro na Atualização LD Projeto Básico: {e}")
        return {
            "ok": False,
            "mensagem": f"Erro na Atualização LD Projeto Básico: {e}",
            "detalhes": {"erro": str(e), "tipo": e.__class__.__name__},
        }

    finally:
        _remover_lock(LOCK_FILE)


if __name__ == "__main__":
    resultado = executar()
    print(resultado.get("mensagem", resultado))
