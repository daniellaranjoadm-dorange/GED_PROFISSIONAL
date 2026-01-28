import os
import shutil
from datetime import datetime, timedelta, date
import xlwings as xw
import re

print("🚀 LDP iniciado")

# ==========================================================
# CONFIGURAÇÕES
# ==========================================================
PLANILHA = r"\\virm-rgr022\FILESERVER\Projetos\05_HANDYMAX\09. Doc Control\3 - LD\I-LD-4880.00-9311-000-CZ1-001_RA.xlsm"

ABA_LD = "LD"
ABA_LD_MARENOVA = "LD MARENOVA"
ABA_MEDICAO = "MEDIÇÃO"  # exatamente como está no Excel

PASTA_DOCS = r"\\virm-rgr022\FILESERVER\Projetos\05_HANDYMAX\09. Doc Control\10 - Engenharia"
PASTA_GRD = r"\\virm-rgr022\FILESERVER\Projetos\05_HANDYMAX\09. Doc Control\1 - DOCS EMISSÃO ENGEDOC\Emitidos"
PASTA_PCF = r"\\virm-rgr022\FILESERVER\Projetos\05_HANDYMAX\09. Doc Control\9 - PCFs Transpetro"
PASTA_PCF_RESPOSTA = r"\\virm-rgr022\FILESERVER\Projetos\05_HANDYMAX\09. Doc Control\9 - PCFs Transpetro\Respostas PCFs MARENOVA"

PASTA_LOGS = r"\\virm-rgr022\FILESERVER\Projetos\05_HANDYMAX\09. Doc Control\3 - LD\Logs"
PASTA_BACKUPS = os.path.join(PASTA_LOGS, "Backups")
os.makedirs(PASTA_BACKUPS, exist_ok=True)
os.makedirs(PASTA_LOGS, exist_ok=True)

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
ULTIMA_COLUNA = "Q"  # na sua LD vai até Q

# Excel constants
xlCenter = -4108
xlLeft = -4131

# ✅ Formato de data desejado no Excel PT-BR (para não aparecer yyyy)
DATE_NUMBERFORMAT_LOCAL = "dd/mm/aaaa"
DATE_NUMBERFORMAT_FALLBACK = "dd/mm/yyyy"  # fallback para ambientes não-PTBR

# ==========================================================
# LOG
# ==========================================================
LOG_FILE = None  # será definido no processar()

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
def backup_planilha():
    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    nome, ext = os.path.splitext(os.path.basename(PLANILHA))
    destino = os.path.join(PASTA_BACKUPS, f"{nome}_BK_{ts}{ext}")
    shutil.copy2(PLANILHA, destino)
    log(f"🔒 Backup criado: {destino}")

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
        for fmt in ("%d/%m/%Y", "%d/%m/%y", "%Y-%m-%d"):
            try:
                return datetime.strptime(s, fmt).date()
            except Exception:
                pass
        return None

    return None

def _aplicar_formato_data(cell):
    """Aplica formato de data respeitando locale PT-BR."""
    try:
        cell.api.NumberFormatLocal = DATE_NUMBERFORMAT_LOCAL
        return
    except Exception:
        pass
    try:
        cell.api.NumberFormat = DATE_NUMBERFORMAT_FALLBACK
    except Exception:
        pass

def setar_data(cell, v):
    """Escreve data como data REAL no Excel e força formato dd/mm/aaaa (PT-BR)."""
    d = _coerce_to_date(v)
    if d is None:
        cell.value = None
        return
    cell.value = d
    _aplicar_formato_data(cell)

def forcar_numberformat_coluna(ws, col_letter, start_row, end_row):
    """Força NumberFormat em uma coluna de datas usando locale PT-BR (sem quebrar)."""
    if end_row < start_row:
        return
    rng = ws.range(f"{col_letter}{start_row}:{col_letter}{end_row}")
    try:
        rng.api.NumberFormatLocal = DATE_NUMBERFORMAT_LOCAL
        return
    except Exception:
        pass
    try:
        rng.api.NumberFormat = DATE_NUMBERFORMAT_FALLBACK
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

# ==========================================================
# EXTRAIR GRD DO CAMINHO
# ==========================================================
def extrair_grd_do_caminho(path):
    m = re.search(r"(GRD-\d+)", path, re.I)
    return m.group(1).upper() if m else ""

# ==========================================================
# HELPERS (HYPERLINK)
# ==========================================================
def limpar_hyperlink(cell):
    try:
        cell.api.Hyperlinks.Delete()
    except Exception:
        pass

def setar_hyperlink(cell, endereco, texto):
    limpar_hyperlink(cell)
    cell.value = texto
    cell.add_hyperlink(endereco, texto)

# ==========================================================
# INDEXADORES
# ==========================================================
def indexar_engenharia_info():
    """
    Retorna:
      idx[codigo][rev] = { "path": pasta_onde_achou, "file": arquivo, "date": mtime_arquivo }
    Se encontrar duplicado (mesmo codigo+rev em lugares diferentes), mantém o mais recente.
    """
    idx = {}
    for root, _, files in os.walk(PASTA_DOCS):
        for f in files:
            nome, ext = os.path.splitext(f)
            if ext.lower() not in EXTENSOES:
                continue
            if "_R" not in nome:
                continue

            codigo, resto = nome.split("_R", 1)
            mrev = re.match(r"([0-9A-Z]+)", str(resto).strip().upper())
            if not mrev:
                continue

            rev = normalizar_rev(mrev.group(1))
            if not rev:
                continue

            full = os.path.join(root, f)
            dt = _file_datetime(full, "MTIME")

            codigo = codigo.strip()
            existente = idx.get(codigo, {}).get(rev)
            if (existente is None) or (dt and dt > existente["date"]):
                idx.setdefault(codigo, {})[rev] = {
                    "path": root,
                    "file": full,
                    "date": dt
                }
    return idx

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

            codigo = codigo.strip()
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
            dt = _file_datetime(caminho, data_origem)

            codigo = codigo.strip()
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
# INSERIR REVISÕES NOVAS (ENGENHARIA) + LOG
# ==========================================================
def inserir_revisoes_novas(ws, idx_eng):
    last = ws.range("B" + str(ws.cells.last_cell.row)).end("up").row

    rev_rows = {}
    all_rows = {}

    for r in range(2, last + 1):
        codigo = str(ws[f"B{r}"].value or "").strip()
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

def aplicar_formatacao(ws):
    # última linha usando coluna B (mais estável)
    last_row = ws.range("B" + str(ws.cells.last_cell.row)).end("up").row
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

        col_N = ws.range(f"N2:N{last_row}")
        col_N.api.FormatConditions.Add(Type=1, Operator=3, Formula1='="Recebida"').Interior.Color = 0xC6EFCE
        col_N.api.FormatConditions.Add(Type=1, Operator=3, Formula1='="Não Recebida"').Interior.Color = 0xFCE4D6
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
    faixa_titulos = ws_origem.range(f"D2:D{last_row_origem}")
    faixa_disc_f  = ws_origem.range(f"F2:F{last_row_origem}")
    faixa_status  = ws_origem.range(f"I2:I{last_row_origem}")
    faixa_data    = ws_origem.range(f"Z2:Z{last_row_origem}")

    codigos_flat = _flatten(faixa_codigos.value)
    titulos_flat = _flatten(faixa_titulos.value)
    disc_f_flat  = _flatten(faixa_disc_f.value)
    status_flat  = _flatten(faixa_status.value)
    datas_flat   = _flatten(faixa_data.value)

    n = min(len(codigos_flat), len(titulos_flat), len(disc_f_flat), len(status_flat), len(datas_flat))
    codigos_flat = codigos_flat[:n]
    titulos_flat = titulos_flat[:n]
    disc_f_flat  = disc_f_flat[:n]
    status_flat  = status_flat[:n]
    datas_flat   = datas_flat[:n]

    vistos = set()
    unicos_codigos = []
    disciplinas_A  = []
    titulos_unicos = []
    disciplinas_F  = []
    status_unicos  = []
    datas_unicas   = []

    for cod, tit, disc, stat, dt in zip(codigos_flat, titulos_flat, disc_f_flat, status_flat, datas_flat):
        if cod in (None, ""):
            continue
        cod_str = str(cod).strip()
        if cod_str and cod_str not in vistos:
            vistos.add(cod_str)
            unicos_codigos.append(cod_str)
            disciplinas_A.append(extrair_disciplina(cod_str))
            titulos_unicos.append(tit)
            disciplinas_F.append(disc)
            status_unicos.append(stat)
            datas_unicas.append(_coerce_to_date(dt))

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

def processar_aba(wb, aba_nome, idx_eng, idx_eng_codigos, idx_grd, idx_pcf, idx_pcf_resp, idx_grd_resp):
    ws = wb.sheets[aba_nome]
    log(f"📄 Processando aba: {aba_nome}")

    # 1) inserir revisões novas vindas da Engenharia
    inserir_revisoes_novas(ws, idx_eng)

    # 2) recalcular última linha depois das inserções
    last = ws.range("B" + str(ws.cells.last_cell.row)).end("up").row

    # 3) preencher status/links
    for r in range(last, 1, -1):
        codigo = str(ws[f"B{r}"].value or "").strip()
        rev = normalizar_rev(ws[f"C{r}"].value)
        if not codigo:
            continue

        # Engenharia hyperlink em B
        info_eng = idx_eng.get(codigo, {}).get(rev)
        if info_eng:
            setar_hyperlink(ws[f"B{r}"], info_eng["path"], codigo)
        else:
            limpar_hyperlink(ws[f"B{r}"])
            ws[f"B{r}"].value = codigo

        ws[f"H{r}"].value = "Recebido" if codigo in idx_eng_codigos else "Não Recebido"

        # GRD (J / K)
        info = idx_grd.get(codigo, {}).get(rev)
        if info:
            ws[f"I{r}"].value = "Emitido"
            setar_hyperlink(ws[f"J{r}"], info["path"], info["grd"])
            _preencher_data_por_modo(ws[f"K{r}"], COL_K_MODO, info.get("date"), OBS_COL_K)

            if LOG_DETALHADO:
                log(f"   [J/K] {aba_nome} L{r} | {codigo}_R{rev} => GRD={info['grd']} | link={info['path']} | K={_fmt_dt(info.get('date'))} | doc={info.get('doc_file','-')} | doc_dt={_fmt_dt(info.get('doc_dt'))} | grd_dt={_fmt_dt(info.get('grd_dt'))}")
        else:
            ws[f"I{r}"].value = "Não Emitido"
            ws[f"J{r}"].value = None
            if (COL_K_MODO or "").upper() != "MANTER":
                ws[f"K{r}"].value = None
            limpar_hyperlink(ws[f"J{r}"])

            if LOG_DETALHADO:
                log(f"   [J/K] {aba_nome} L{r} | {codigo}_R{rev} => GRD NÃO encontrado")

        # PCF normal (L / M) - SEM subpasta de respostas
        info_pcf = None
        mapa = idx_pcf.get(codigo, {})
        rev_doc = normalizar_rev(ws[f"C{r}"].value)
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
            setar_hyperlink(ws[f"L{r}"], info_pcf["path"], info_pcf["pcf"])
            _preencher_data_por_modo(ws[f"M{r}"], COL_M_MODO, info_pcf.get("date"), OBS_COL_M)
            ws[f"N{r}"].value = "Recebida"

            if LOG_DETALHADO:
                log(f"   [L/M] {aba_nome} L{r} | {codigo}_R{rev_doc} => PCF base='{rev_doc}' escolheu rev_pcf='{info_pcf.get('rev','-')}' (maior sufixo) | file={info_pcf['pcf']} | M={_fmt_dt(info_pcf.get('date'))}")
        else:
            ws[f"L{r}"].value = None
            if (COL_M_MODO or "").upper() != "MANTER":
                ws[f"M{r}"].value = None
            ws[f"N{r}"].value = "Não Recebida"
            limpar_hyperlink(ws[f"L{r}"])

            if LOG_DETALHADO:
                log(f"   [L/M] {aba_nome} L{r} | {codigo}_R{rev_doc} => PCF NÃO encontrada")

        # PCF resposta (O / P) - SOMENTE subpasta de respostas
        info_resp = None
        mapa_resp = idx_pcf_resp.get(codigo, {})
        rev_doc = normalizar_rev(ws[f"C{r}"].value)
        best = None
        best_key = None

        if mapa_resp and rev_doc:
            base = (rev_doc or "").strip().upper()
            for rev_pcf, cand in mapa_resp.items():
                ok, sufixo = _split_by_base(rev_pcf, base)
                if not ok:
                    continue

                dtcand = cand.get("date")
                if dtcand is None:
                    dtcand = datetime(1900, 1, 1)

                k = (_suffix_key(sufixo), dtcand)
                if (best_key is None) or (k[0] > best_key[0]) or (k[0] == best_key[0] and k[1] > best_key[1]):
                    best_key = k
                    best = cand

        info_resp = best
        if info_resp:
            setar_hyperlink(ws[f"O{r}"], info_resp["path"], info_resp["pcf"])
            _preencher_data_por_modo(ws[f"P{r}"], COL_P_MODO, info_resp.get("date"), OBS_COL_P)

            # Q = GRD correspondente ao arquivo PCF encontrado
            grd_resp = idx_grd_resp.get(info_resp["pcf"].upper(), "")
            if grd_resp:
                setar_hyperlink(ws[f"Q{r}"], os.path.join(PASTA_GRD, grd_resp), grd_resp)
            else:
                ws[f"Q{r}"].value = None
                limpar_hyperlink(ws[f"Q{r}"])

            if LOG_DETALHADO:
                log(f"   [O/P/Q] {aba_nome} L{r} | {codigo}_R{rev_doc} => PCF_RESP base='{rev_doc}' escolheu rev_pcf='{info_resp.get('rev','-')}' | file={info_resp['pcf']} | P={_fmt_dt(info_resp.get('date'))} | Q_GRD={grd_resp or '-'}")
        else:
            ws[f"O{r}"].value = None
            if (COL_P_MODO or "").upper() != "MANTER":
                ws[f"P{r}"].value = None
            ws[f"Q{r}"].value = None
            limpar_hyperlink(ws[f"O{r}"])
            limpar_hyperlink(ws[f"Q{r}"])

            if LOG_DETALHADO:
                log(f"   [O/P/Q] {aba_nome} L{r} | {codigo}_R{rev} => PCF_RESPOSTA NÃO encontrada")

    # 4) formatar
    if APLICAR_FORMATACAO:
        aplicar_formatacao(ws)

# ==========================================================
# PROCESSAMENTO
# ==========================================================
def processar():
    global LOG_FILE
    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    LOG_FILE = os.path.join(PASTA_LOGS, f"LDP_{ts}.log")
    log(f"🧾 Log: {LOG_FILE}")

    backup_planilha()

    log("🔎 Indexando Engenharia (código + revisão + pasta)...")
    idx_eng = indexar_engenharia_info()
    idx_eng_codigos = set(idx_eng.keys())
    log(f"   - Códigos na Engenharia: {len(idx_eng_codigos)}")

    log("🔎 Indexando GRDs/PCFs...")
    idx_grd = indexar_grds()

    # ✅ PCF normal (L/M): EXCLUI a subpasta de respostas
    idx_pcf = indexar_pcfs(PASTA_PCF, excluir_subpastas=[PASTA_PCF_RESPOSTA], data_origem=DATA_PCF_ORIGEM)

    # ✅ PCF resposta (O/P): SOMENTE a pasta de respostas
    idx_pcf_resp = indexar_pcfs(PASTA_PCF_RESPOSTA, data_origem=DATA_PCF_RESP_ORIGEM)

    # ✅ Mapa PCF -> GRD para preencher Q
    idx_grd_resp = indexar_grd_resposta_pcf()

    with xw.App(visible=False, add_book=False) as app:
        app.display_alerts = False
        app.screen_updating = False

        wb = app.books.open(PLANILHA)

        processar_aba(wb, ABA_LD, idx_eng, idx_eng_codigos, idx_grd, idx_pcf, idx_pcf_resp, idx_grd_resp)
        processar_aba(wb, ABA_LD_MARENOVA, idx_eng, idx_eng_codigos, idx_grd, idx_pcf, idx_pcf_resp, idx_grd_resp)

        atualizar_medicao(wb, ABA_LD)

        wb.save()
        wb.close()

    log("✅ LDP finalizado com sucesso!")

# ==========================================================
# EXECUÇÃO
# ==========================================================
if __name__ == "__main__":
    processar()
