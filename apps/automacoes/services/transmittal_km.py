import re
import os
import shutil
from datetime import datetime
from apps.automacoes.models import TransmittalKM, ExecucaoAutomacao
from apps.automacoes.services.document_link_engine import executar_vinculo_km_ld
from pathlib import Path
from typing import Dict, List, Tuple
from django.utils import timezone
from openpyxl import Workbook
from openpyxl.styles import Font, PatternFill
import xlwings as xw


PASTA_PDFS = Path(
    r"\\virm-rgr022\FILESERVER\Projetos\05_HANDYMAX\09. Doc Control\15 - Documentos KM\0 Transmittal Letters\Transmittal Letters"
)

ARQUIVO_EXCEL_NOVO = Path(
    r"\\virm-rgr022\FILESERVER\Projetos\05_HANDYMAX\09. Doc Control\15 - Documentos KM\0 Transmittal Letters\Transmittal Letters\Lista de Docs recebidos KM - NOVA.xlsx"
)

# LD MASTER: a lista KM passa a ser atualizada diretamente dentro da LD.
PLANILHA_LD = Path(
    r"\\virm-rgr022\FILESERVER\Projetos\05_HANDYMAX\09. Doc Control\3 - LD\I-LD-4880.00-9311-000-CZ1-001_RD.xlsm"
)
ABA_LD_LISTA_KM = "Lista de Docs recebidos KM"
PASTA_LOGS_LD = PLANILHA_LD.parent / "Logs"
PASTA_BACKUPS_LD = PASTA_LOGS_LD / "Backups"

ABA_PLANILHA = "Planilha1"
ABA_LOG = "LOG"

CABECALHOS = [
    "Documento",
    "Titulo",
    "Pasta",
    "Emissão",
    "Proposito de Emissão",
    "Data Envio",
    "Transmittal N°",
]

PROPOSITOS_CONHECIDOS = [
    "Send Update without Approval",
    "Send for Re-Approval",
    "Send for Approval",
    "Send for Information",
    "Send Preliminary",
    "For Approval",
    "For Information",
]

# Identificador dos documentos KM. Há famílias somente com hífens
# (630-051) e famílias mistas com hífen e pontos (263-433.100.01).
# Cada separador precisa ser seguido por um bloco numérico para não capturar
# o hífen que inicia o título do documento.
PADRAO_DOCUMENTO_KM = r"[0-9]{3,4}(?:[-.][0-9]{2,4})+"

PREENCHIMENTO_AMARELO = PatternFill(fill_type="solid", fgColor="FFF2CC")
PREENCHIMENTO_VERMELHO = PatternFill(fill_type="solid", fgColor="F4CCCC")
FONTE_LINK = Font(color="0563C1", underline="single")
pdfplumber = None


def normalizar_data(texto: str) -> str:
    """
    Normaliza Data Envio para o padrão oficial da LD: dd/mm/aaaa.

    Os Transmittals podem vir como:
    - dd-mm-aaaa
    - dd.mm.aaaa
    - dd/mm/aaaa
    - aaaa-mm-dd

    A saída fica sempre como texto com barras, evitando que o Excel converta
    automaticamente para formatos regionais diferentes.
    """
    if not texto:
        return ""

    s = str(texto).strip()

    # ISO: aaaa-mm-dd -> dd/mm/aaaa
    m_iso = re.search(r"\b(\d{4})-(\d{2})-(\d{2})\b", s)
    if m_iso:
        ano, mes, dia = m_iso.groups()
        return f"{dia}/{mes}/{ano}"

    # Formatos TP/KM: dd-mm-aaaa, dd.mm.aaaa ou dd/mm/aaaa -> dd/mm/aaaa
    m = re.search(r"\b(\d{2})[-./](\d{2})[-./](\d{4})\b", s)
    if m:
        dia, mes, ano = m.groups()
        return f"{dia}/{mes}/{ano}"

    return s


def limpar_valor(valor: str) -> str:
    if not valor:
        return ""
    valor = valor.strip(" -;\n\t")
    valor = re.sub(r"\s+", " ", valor)
    return valor.strip()




def normalizar_documento_chave(valor: str) -> str:
    """
    Chave operacional do documento KM.

    A planilha de transmittal não possui revisão formal por linha.
    Portanto, o documento único é a coluna Documento normalizada.
    """
    if isinstance(valor, float) and valor.is_integer():
        valor = str(int(valor))
    elif isinstance(valor, int):
        valor = str(valor)
    else:
        valor = str(valor or "")
    valor = limpar_valor(valor).upper()
    return re.sub(r"\s+", "", valor)


def chave_documento_transmittal(dados: dict) -> tuple[str, str]:
    """Identidade usada para reconciliar banco, PDF e linhas efetivamente gravadas na LD."""
    return (
        normalizar_documento_chave(dados.get("Documento", "")),
        limpar_valor(str(dados.get("Transmittal N°", ""))).upper(),
    )


def dados_transmittal_model(obj: TransmittalKM) -> Dict[str, str]:
    return {
        "Documento": obj.documento or "",
        "Titulo": obj.titulo or "",
        "Pasta": obj.pasta or "",
        "Emissão": obj.emissao or "",
        "Proposito de Emissão": obj.proposito_emissao or "",
        "Data Envio": obj.data_envio or "",
        "Transmittal N°": obj.transmittal_numero or "",
        "Arquivo PDF": obj.arquivo_pdf or "",
        "Status Parse": obj.status_parse or "",
        "Observação Parse": obj.observacao_parse or "",
    }


def _data_envio_sort_key(valor: str):
    """
    Converte Data Envio para chave comparável.

    Formatos esperados:
    - dd-mm-aaaa, gerado por normalizar_data()
    - dd.mm.aaaa, vindo direto do PDF
    - aaaa-mm-dd, caso venha do banco/Excel em formato ISO
    """
    texto = limpar_valor(str(valor or ""))
    if not texto:
        return (0, 0, 0)

    m = re.search(r"\b(\d{2})[-./](\d{2})[-./](\d{4})\b", texto)
    if m:
        dia, mes, ano = m.groups()
        return (int(ano), int(mes), int(dia))

    m = re.search(r"\b(\d{4})-(\d{2})-(\d{2})\b", texto)
    if m:
        ano, mes, dia = m.groups()
        return (int(ano), int(mes), int(dia))

    return (0, 0, 0)


def _transmittal_sort_key(valor: str) -> tuple:
    """Compara toda a sequência numérica, inclusive o número após TR."""
    texto = limpar_valor(str(valor or "")).upper()
    numeros = tuple(int(parte) for parte in re.findall(r"\d+", texto))
    return numeros or (0,)


def _caminho_normalizado(caminho) -> str:
    return os.path.normcase(os.path.normpath(str(caminho or "").strip()))


def _registro_pertence_aos_pdfs_atuais(dados: dict, caminhos_pdfs: set[str]) -> bool:
    """Aceita somente registros cujo PDF existe no inventário atual da pasta oficial."""
    caminho = _caminho_normalizado(dados.get("Arquivo PDF", ""))
    return bool(caminho and caminho in caminhos_pdfs)


def _registro_mais_recente(novo: dict, atual: dict) -> bool:
    """
    Define se o novo registro deve substituir o atual.

    Critério oficial:
    1. maior Data Envio;
    2. empate: maior Transmittal N°;
    3. empate: último registro processado.
    """
    data_nova = _data_envio_sort_key(novo.get("Data Envio", ""))
    data_atual = _data_envio_sort_key(atual.get("Data Envio", ""))

    if data_nova != data_atual:
        return data_nova > data_atual

    trans_novo = _transmittal_sort_key(novo.get("Transmittal N°", ""))
    trans_atual = _transmittal_sort_key(atual.get("Transmittal N°", ""))

    if trans_novo != trans_atual:
        return trans_novo > trans_atual

    return True


def filtrar_registros_latest_por_documento(registros: List[Dict[str, str]]) -> Tuple[List[Dict[str, str]], int]:
    """
    Mantém somente o registro mais recente por documento KM.

    A coluna A da planilha é o cadastro do documento.
    Como não existe revisão formal, registros duplicados representam atualizações.
    """
    latest = {}
    duplicados = 0

    for dados in registros:
        chave = normalizar_documento_chave(dados.get("Documento", ""))
        if not chave:
            continue

        atual = latest.get(chave)
        if atual is None:
            latest[chave] = dados
            continue

        duplicados += 1
        if _registro_mais_recente(dados, atual):
            latest[chave] = dados

    ordenados = sorted(
        latest.values(),
        key=lambda item: (
            normalizar_documento_chave(item.get("Documento", "")),
            _data_envio_sort_key(item.get("Data Envio", "")),
            _transmittal_sort_key(item.get("Transmittal N°", "")),
        ),
    )
    return ordenados, duplicados


def extrair_texto_pdf(caminho_pdf: Path) -> str:
    textos = []
    try:
        with pdfplumber.open(caminho_pdf) as pdf:
            for pagina in pdf.pages:
                texto = pagina.extract_text()
                if texto:
                    textos.append(texto)
    except Exception as e:
        print(f"[ERRO] Falha ao ler PDF {caminho_pdf.name}: {e}")
        return ""
    return "\n".join(textos)


def normalizar_texto(texto: str) -> str:
    texto = texto.replace("\r", "\n").replace("\xa0", " ")
    texto = re.sub(r"[ \t]+", " ", texto)

    correcoes = [
        (r"Send Update without\s*\n\s*Approval", "Send Update without Approval"),
        (r"Send for Re-\s*\n\s*Approval", "Send for Re-Approval"),
        (r"Send for\s*\n\s*Approval", "Send for Approval"),
        (r"Send for\s*\n\s*Information", "Send for Information"),
        (r"Send\s*\n\s*Preliminary", "Send Preliminary"),
        (r"For\s*\n\s*Approval", "For Approval"),
        (r"For\s*\n\s*Information", "For Information"),
    ]

    for padrao, substituicao in correcoes:
        texto = re.sub(padrao, substituicao, texto, flags=re.IGNORECASE)

    texto = re.sub(r"\n+", "\n", texto)
    return texto.strip()


def extrair_transmittal(texto: str, nome_arquivo: str) -> str:
    m = re.search(r"Transmittal number:\s*([0-9]+)", texto, re.IGNORECASE)
    if m:
        return f"T-{m.group(1).strip()}"

    m = re.search(r"^T-([0-9]+)", nome_arquivo, re.IGNORECASE)
    if m:
        return f"T-{m.group(1).strip()}"

    return ""


def extrair_data_envio(texto: str) -> str:
    m = re.search(r"Sent By:\s*.*?,\s*(\d{2}\.\d{2}\.\d{4})", texto, re.IGNORECASE)
    if m:
        return normalizar_data(m.group(1))

    datas = re.findall(r"\b\d{2}\.\d{2}\.\d{4}\b", texto)
    return normalizar_data(datas[0]) if datas else ""


def extrair_bloco_document_information(texto: str) -> str:
    padroes_fim = [
        r"\nSent By:",
        r"\nTotal attachments:",
        r"\nPage \d+ of \d+",
        r"\nPlease find attached",
        r"\nThis transmittal",
    ]

    inicio = re.search(r"Document Information", texto, re.IGNORECASE)
    if not inicio:
        return texto

    trecho = texto[inicio.end() :]
    fim_pos = None

    for padrao in padroes_fim:
        m = re.search(padrao, trecho, re.IGNORECASE)
        if m:
            pos = m.start()
            if fim_pos is None or pos < fim_pos:
                fim_pos = pos

    if fim_pos is not None:
        trecho = trecho[:fim_pos]

    return trecho.strip()


def identificar_proposito_em_texto(texto: str) -> str:
    for prop in sorted(PROPOSITOS_CONHECIDOS, key=len, reverse=True):
        if re.search(re.escape(prop), texto, re.IGNORECASE):
            return prop
    return ""


def separar_emissao_e_proposito(comment_texto: str) -> Tuple[str, str]:
    comment_texto = limpar_valor(comment_texto)

    proposito = identificar_proposito_em_texto(comment_texto)
    if proposito:
        idx = re.search(re.escape(proposito), comment_texto, re.IGNORECASE)
        if idx:
            emissao = limpar_valor(comment_texto[: idx.start()])
            return emissao, proposito

    for prop in PROPOSITOS_CONHECIDOS:
        if comment_texto.lower() == prop.lower():
            return "", prop

    if comment_texto.lower() == "not applicable":
        return "Not applicable", ""

    return comment_texto, ""


def encontrar_documentos_no_bloco(bloco: str) -> List[Dict[str, str]]:
    resultados = []

    # Alguns relatórios quebram título/pasta em duas ou mais linhas. Captura o
    # bloco inteiro até "Comment:" antes do fallback linha a linha.
    padrao_multilinha = re.compile(
        rf"(?m)^({PADRAO_DOCUMENTO_KM})(?:-ETS)?[- ]+"
        r"(.+?)\s+\(([^)]+)\)\s*(?=\nComment:)",
        re.IGNORECASE | re.DOTALL,
    )
    for m in padrao_multilinha.finditer(bloco):
        resultados.append(
            {
                "Documento": limpar_valor(m.group(1)),
                "Titulo": limpar_valor(m.group(2)),
                "Pasta": limpar_valor(m.group(3)),
            }
        )

    linhas = [limpar_valor(l) for l in bloco.splitlines() if limpar_valor(l)]

    for linha in linhas:
        if re.search(
            r"^(Comment:|Rev\.?|Revision|Purpose|Scale|Format|Total|Sent By:)",
            linha,
            re.IGNORECASE,
        ):
            continue

        m = re.match(
            rf"^({PADRAO_DOCUMENTO_KM})(?:-ETS)?[- ]+(.+?)\s+\(([^)]+)\)$",
            linha,
            re.IGNORECASE,
        )
        if m:
            resultados.append(
                {
                    "Documento": limpar_valor(m.group(1)),
                    "Titulo": limpar_valor(m.group(2)),
                    "Pasta": limpar_valor(m.group(3)),
                }
            )

    vistos = set()
    unicos = []
    for item in resultados:
        chave = (item["Documento"], item["Titulo"], item["Pasta"])
        if chave not in vistos:
            vistos.add(chave)
            unicos.append(item)

    return unicos


def extrair_comment_global(bloco: str) -> str:
    m = re.search(r"Comment:\s*(.+)", bloco, re.IGNORECASE | re.DOTALL)
    if not m:
        return ""

    comment = m.group(1)

    for marcador in ["Rev.", "Revision", "Scale", "Format", "Size", "A3", "A4", "A1"]:
        pos = re.search(rf"\b{re.escape(marcador)}\b", comment, re.IGNORECASE)
        if pos:
            comment = comment[: pos.start()]
            break

    return limpar_valor(comment)


def extrair_registros_pdf(texto: str, nome_arquivo: str, caminho_pdf: Path) -> List[Dict[str, str]]:
    texto = normalizar_texto(texto)
    bloco = extrair_bloco_document_information(texto)

    transmittal = extrair_transmittal(texto, nome_arquivo)
    data_envio = extrair_data_envio(texto)

    documentos = encontrar_documentos_no_bloco(bloco)
    comment_global = extrair_comment_global(bloco)
    emissao_global, proposito_global = separar_emissao_e_proposito(comment_global)

    registros = []

    if documentos:
        for doc in documentos:
            registros.append(
                {
                    "Documento": doc["Documento"],
                    "Titulo": doc["Titulo"],
                    "Pasta": doc["Pasta"],
                    "Emissão": emissao_global,
                    "Proposito de Emissão": proposito_global,
                    "Data Envio": data_envio,
                    "Transmittal N°": transmittal,
                    "Arquivo PDF": str(caminho_pdf),
                    "Status Parse": "OK",
                    "Observação Parse": "",
                }
            )
        return registros

    m_nome = re.search(
        rf"\d{{2}}-\d{{4}}-\d{{2}}-({PADRAO_DOCUMENTO_KM})(?:-ETS)?[- ]+(.+?);\s*(.+?)\.pdf$",
        nome_arquivo,
        re.IGNORECASE,
    )
    if m_nome:
        emissao_nome, proposito_nome = separar_emissao_e_proposito(limpar_valor(m_nome.group(3)))
        registros.append(
            {
                "Documento": limpar_valor(m_nome.group(1)),
                "Titulo": limpar_valor(m_nome.group(2)),
                "Pasta": "",
                "Emissão": emissao_nome or emissao_global,
                "Proposito de Emissão": proposito_nome or proposito_global,
                "Data Envio": data_envio,
                "Transmittal N°": transmittal,
                "Arquivo PDF": str(caminho_pdf),
                "Status Parse": "PARCIAL",
                "Observação Parse": "Registro montado com fallback pelo nome do arquivo.",
            }
        )
        return registros

    registros.append(
        {
            "Documento": "",
            "Titulo": Path(nome_arquivo).stem,
            "Pasta": "",
            "Emissão": emissao_global,
            "Proposito de Emissão": proposito_global,
            "Data Envio": data_envio,
            "Transmittal N°": transmittal,
            "Arquivo PDF": str(caminho_pdf),
            "Status Parse": "FALHA",
            "Observação Parse": "Não foi possível identificar o bloco de documentos.",
        }
    )
    return registros


def criar_planilha_nova():
    wb = Workbook()
    ws = wb.active
    ws.title = ABA_PLANILHA
    ws_log = wb.create_sheet(ABA_LOG)

    for i, nome in enumerate(CABECALHOS, start=1):
        ws.cell(row=1, column=i).value = nome

    cab_log = ["Arquivo PDF", "Transmittal N°", "Status", "Mensagem"]
    for i, nome in enumerate(cab_log, start=1):
        ws_log.cell(row=1, column=i).value = nome

    return wb, ws, ws_log


def aplicar_link_nativo(celula, texto_exibido: str, arquivo_pdf: str):
    celula.value = texto_exibido if texto_exibido else ""
    if arquivo_pdf and texto_exibido:
        celula.hyperlink = arquivo_pdf
        celula.font = FONTE_LINK


def destacar_linha(ws, linha: int, dados: dict):
    campos_criticos = {
        1: dados.get("Documento", ""),
        2: dados.get("Titulo", ""),
        3: dados.get("Pasta", ""),
        5: dados.get("Proposito de Emissão", ""),
        6: dados.get("Data Envio", ""),
        7: dados.get("Transmittal N°", ""),
    }

    for coluna, valor in campos_criticos.items():
        if not str(valor).strip():
            ws.cell(linha, coluna).fill = PREENCHIMENTO_AMARELO

    if dados.get("Status Parse") == "FALHA":
        for coluna in range(1, 8):
            ws.cell(linha, coluna).fill = PREENCHIMENTO_VERMELHO


def adicionar_linha(ws, dados: dict):
    linha = ws.max_row + 1
    arquivo_pdf = dados.get("Arquivo PDF", "")

    aplicar_link_nativo(ws.cell(linha, 1), dados["Documento"], arquivo_pdf)
    ws.cell(linha, 2).value = dados["Titulo"]
    ws.cell(linha, 3).value = dados["Pasta"]
    ws.cell(linha, 4).value = dados["Emissão"]
    ws.cell(linha, 5).value = dados["Proposito de Emissão"]

    cel_data = ws.cell(linha, 6)
    cel_data.value = normalizar_data(dados["Data Envio"])
    cel_data.number_format = "@"

    aplicar_link_nativo(ws.cell(linha, 7), dados["Transmittal N°"], arquivo_pdf)

    destacar_linha(ws, linha, dados)


def registrar_log(ws_log, arquivo_pdf: str, transmittal: str, status: str, mensagem: str):
    linha = ws_log.max_row + 1
    ws_log.cell(linha, 1).value = Path(arquivo_pdf).name if arquivo_pdf else ""
    ws_log.cell(linha, 2).value = transmittal
    ws_log.cell(linha, 3).value = status
    ws_log.cell(linha, 4).value = mensagem

    if status in {"FALHA", "ERRO"}:
        for coluna in range(1, 5):
            ws_log.cell(linha, coluna).fill = PREENCHIMENTO_VERMELHO
    elif status in {"PARCIAL", "AVISO"}:
        for coluna in range(1, 5):
            ws_log.cell(linha, coluna).fill = PREENCHIMENTO_AMARELO


def ajustar_largura(ws):
    larguras = {
        "A": 20,
        "B": 65,
        "C": 22,
        "D": 25,
        "E": 32,
        "F": 15,
        "G": 18,
    }
    for col, largura in larguras.items():
        ws.column_dimensions[col].width = largura


def ajustar_largura_log(ws_log):
    larguras = {
        "A": 28,
        "B": 18,
        "C": 14,
        "D": 90,
    }
    for col, largura in larguras.items():
        ws_log.column_dimensions[col].width = largura



def salvar_no_banco(dados: dict, arquivos_pdf_oficiais=None):
    documento = dados.get("Documento", "").strip()
    transmittal = dados.get("Transmittal N°", "").strip()

    if not documento:
        return False

    # Regra oficial: manter somente o registro mais recente por documento.
    # A deduplicação é feita antes de salvar; esta limpeza remove históricos antigos
    # do banco quando o mesmo documento já existia em outro Transmittal.
    antigos = TransmittalKM.objects.filter(documento__iexact=documento).exclude(
        transmittal_numero=transmittal
    )
    if arquivos_pdf_oficiais is not None:
        antigos = antigos.filter(arquivo_pdf__in=list(arquivos_pdf_oficiais))
    antigos.delete()

    TransmittalKM.objects.update_or_create(
        documento=documento,
        transmittal_numero=transmittal,
        defaults={
            "titulo": dados.get("Titulo", ""),
            "pasta": dados.get("Pasta", ""),
            "emissao": dados.get("Emissão", ""),
            "proposito_emissao": dados.get("Proposito de Emissão", ""),
            "data_envio": normalizar_data(dados.get("Data Envio", "")),
            "arquivo_pdf": dados.get("Arquivo PDF", ""),
            "status_parse": dados.get("Status Parse", ""),
            "observacao_parse": dados.get("Observação Parse", ""),
        },
    )
    return True



# ==========================================================
# EXPORTAÇÃO DIRETA PARA LD MASTER
# ==========================================================
def normalizar_endereco_hyperlink(endereco: str) -> str:
    """
    Grava links de rede como UNC puro, evitando file:/// no Excel.
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

    while s.startswith("/") and not s.startswith("//"):
        s = s[1:]

    if s.startswith("//"):
        s = "\\\\" + s.lstrip("/").replace("/", "\\")

    return s


def backup_ld_master() -> str:
    """
    Cria backup da LD antes de sobrescrever a aba Lista de Docs recebidos KM.
    """
    PASTA_BACKUPS_LD.mkdir(parents=True, exist_ok=True)

    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    nome = PLANILHA_LD.stem
    ext = PLANILHA_LD.suffix
    destino = PASTA_BACKUPS_LD / f"{nome}_BK_KM_TRANSMITTAL_{ts}{ext}"

    shutil.copy2(str(PLANILHA_LD), str(destino))
    print(f"[INFO] Backup LD criado antes da atualização KM: {destino}")

    return str(destino)


def obter_linhas_existentes_ld() -> list:
    """Retorna os campos A:G de cada linha efetivamente gravada na LD."""
    if not PLANILHA_LD.exists():
        return []

    with xw.App(visible=False, add_book=False) as app:
        app.display_alerts = False
        app.screen_updating = False
        wb = app.books.open(str(PLANILHA_LD), update_links=False, read_only=True)
        try:
            try:
                ws = wb.sheets[ABA_LD_LISTA_KM]
            except Exception:
                return []

            # End(xlUp) respeita filtros ativos e pode parar na última linha
            # visível, ignorando documentos gravados em linhas filtradas/ocultas.
            # O UsedRange fornece o limite físico real; as linhas vazias são
            # descartadas logo abaixo pela própria compreensão da lista.
            ultima_linha = int(ws.used_range.last_cell.row)
            if ultima_linha < 2:
                return []

            valores = ws.range(f"A2:G{ultima_linha}").value
            if not isinstance(valores, list):
                valores = [valores]
            elif valores and not isinstance(valores[0], list):
                valores = [valores]

            return [
                {
                    "Documento": linha[0] or "",
                    "Titulo": linha[1] or "",
                    "Pasta": linha[2] or "",
                    "Emissão": linha[3] or "",
                    "Proposito de Emissão": linha[4] or "",
                    "Data Envio": normalizar_data(linha[5] or ""),
                    "Transmittal N°": linha[6] or "",
                }
                for linha in valores
                if isinstance(linha, list) and len(linha) > 6 and linha[0] and linha[6]
            ]
        finally:
            wb.close()


def obter_registros_existentes_ld() -> set:
    """Retorna as chaves Documento + Transmittal realmente gravadas na LD."""
    return {chave_documento_transmittal(item) for item in obter_linhas_existentes_ld()}


def obter_transmittals_existentes_ld() -> set:
    """Compatibilidade: retorna os transmittals confirmados na LD."""
    return {transmittal for _, transmittal in obter_registros_existentes_ld() if transmittal}


def _limpar_hyperlink_xlwings(cell):
    try:
        cell.api.Hyperlinks.Delete()
    except Exception:
        pass


def _setar_hyperlink_xlwings(cell, texto: str, endereco: str):
    texto = str(texto or "").strip()
    endereco = normalizar_endereco_hyperlink(endereco)

    _limpar_hyperlink_xlwings(cell)
    cell.value = texto

    if not texto or not endereco:
        return

    try:
        cell.api.Hyperlinks.Add(
            Anchor=cell.api,
            Address=endereco,
            TextToDisplay=texto,
        )
    except Exception:
        try:
            cell.add_hyperlink(endereco, texto)
        except Exception:
            pass


def atualizar_lista_km_dentro_ld(registros_latest: List[Dict[str, str]]) -> Dict[str, object]:
    """Reconstrói A:G com uma linha mais recente por documento da pasta oficial."""
    if not PLANILHA_LD.exists():
        raise FileNotFoundError(f"LD Master não encontrada: {PLANILHA_LD}")

    if not registros_latest:
        raise RuntimeError(
            "A consolidação KM não retornou registros da pasta oficial. "
            "A aba existente foi preservada integralmente."
        )

    backup_path = backup_ld_master()
    wb = None
    arquivo_alterado = False
    esperados_por_documento = {
        normalizar_documento_chave(dados.get("Documento", "")): dados
        for dados in registros_latest
    }

    try:
        with xw.App(visible=False, add_book=False) as app:
            app.display_alerts = False
            app.screen_updating = False
            # Impede macros/eventos da LD de reporem valores anteriores enquanto
            # a aba é reconstruída programaticamente.
            app.enable_events = False
            try:
                app.calculation = "manual"
            except Exception:
                # Algumas instalações do Excel bloqueiam a troca global do modo
                # de cálculo; a escrita explícita por célula continua segura.
                pass

            wb = app.books.open(
                str(PLANILHA_LD),
                update_links=False,
                ignore_read_only_recommended=True,
            )
            if bool(wb.api.ReadOnly):
                raise RuntimeError(
                    "A LD está aberta em outra instância/usuário e foi carregada como somente leitura. "
                    "Feche a planilha antes de executar o Transmittal KM."
                )

            try:
                ws = wb.sheets[ABA_LD_LISTA_KM]
            except Exception:
                ws = wb.sheets.add(ABA_LD_LISTA_KM, after=wb.sheets[-1])
                print(f"[INFO] Aba criada na LD: {ABA_LD_LISTA_KM}")

            ws.range("A1").value = [CABECALHOS]

            linhas = []
            for dados in registros_latest:
                linhas.append([
                    dados.get("Documento", ""),
                    dados.get("Titulo", ""),
                    dados.get("Pasta", ""),
                    dados.get("Emissão", ""),
                    dados.get("Proposito de Emissão", ""),
                    normalizar_data(dados.get("Data Envio", "")),
                    dados.get("Transmittal N°", ""),
                ])

            # Força a coluna F como texto antes de gravar para preservar dd/mm/aaaa
            # exatamente com barras, sem conversão automática do Excel.
            try:
                ws.range("F:F").api.NumberFormat = "@"
            except Exception:
                pass

            ultima_por_coluna = [
                int(ws.range(f"{col}{ws.cells.last_cell.row}").end("up").row)
                for col in "ABCDEFG"
            ]
            ultima_linha_antiga = max(ultima_por_coluna + [1])
            primeira_linha_nova = 2

            # Limpa somente o conteúdo operacional A:G. Outras colunas, abas,
            # fórmulas e formatações do arquivo permanecem intocadas.
            if ultima_linha_antiga >= 2:
                ws.range(f"A2:G{ultima_linha_antiga}").clear_contents()

            if linhas:
                ws.range(f"A{primeira_linha_nova}").value = linhas

            last_row = max(1, primeira_linha_nova + len(linhas) - 1)

            # Hyperlinks nativos em A e G.
            for idx, dados in enumerate(registros_latest, start=primeira_linha_nova):
                arquivo_pdf = dados.get("Arquivo PDF", "")
                _setar_hyperlink_xlwings(ws[f"A{idx}"], dados.get("Documento", ""), arquivo_pdf)
                _setar_hyperlink_xlwings(ws[f"G{idx}"], dados.get("Transmittal N°", ""), arquivo_pdf)

                # Reforça os campos sem hyperlink após a escrita em lote. Em
                # arquivos XLSM extensos, o Excel pode reaproveitar valores das
                # linhas antigas durante a expansão do intervalo.
                valores_diretos = (
                    dados.get("Titulo", ""),
                    dados.get("Pasta", ""),
                    dados.get("Emissão", ""),
                    dados.get("Proposito de Emissão", ""),
                    normalizar_data(dados.get("Data Envio", "")),
                )
                for coluna, valor in zip("BCDEF", valores_diretos):
                    celula = ws[f"{coluna}{idx}"]
                    if coluna == "F":
                        celula.api.NumberFormat = "@"
                    celula.api.Value2 = str(valor or "")

            # Formatação básica enterprise.
            rng = ws.range(f"A{primeira_linha_nova}:G{last_row}") if linhas else ws.range("A1:G1")
            try:
                rng.api.Font.Name = "Arial"
                rng.api.Font.Size = 11
                rng.api.VerticalAlignment = -4108
                rng.api.HorizontalAlignment = -4108
            except Exception:
                pass

            try:
                header = ws.range("A1:G1")
                header.api.Font.Bold = True
                header.api.Interior.Color = 0x1F4E78
                header.api.Font.Color = 0xFFFFFF
            except Exception:
                pass

            try:
                if linhas:
                    ws.range(f"B{primeira_linha_nova}:B{last_row}").api.HorizontalAlignment = -4131
            except Exception:
                pass

            try:
                if linhas:
                    ws.range(f"F{primeira_linha_nova}:F{last_row}").api.NumberFormat = "@"
            except Exception:
                pass

            try:
                tabelas = ws.api.ListObjects
                if tabelas.Count > 0:
                    tabelas.Item(1).Resize(ws.range(f"A1:G{last_row}").api)
                elif not ws.api.AutoFilterMode:
                    ws.range(f"A1:G{last_row}").api.AutoFilter()
            except Exception:
                pass

            wb.save()
            arquivo_alterado = True

            # Fecha explicitamente o workbook antes da validação independente.
            # Em arquivos de rede, sair apenas do contexto do Excel pode deixar o
            # flush do Save pendente e a reabertura imediata enxergar a versão anterior.
            wb.close()
            wb = None

        # Validação independente: fecha o Excel, reabre o arquivo salvo e só então
        # confirma a operação. Isso detecta salvamento silencioso em modo somente leitura.
        linhas_depois = obter_linhas_existentes_ld()
        atuais_por_documento = {
            normalizar_documento_chave(item.get("Documento", "")): item
            for item in linhas_depois
        }
        ausentes = set(esperados_por_documento) - set(atuais_por_documento)
        inesperadas = set(atuais_por_documento) - set(esperados_por_documento)
        divergencias = []
        campos_validacao = (
            "Titulo",
            "Pasta",
            "Emissão",
            "Proposito de Emissão",
            "Data Envio",
            "Transmittal N°",
        )
        for documento in set(esperados_por_documento) & set(atuais_por_documento):
            esperado = esperados_por_documento[documento]
            atual = atuais_por_documento[documento]
            for campo in campos_validacao:
                if campo == "Data Envio":
                    valor_esperado = normalizar_data(esperado.get(campo, ""))
                    valor_atual = normalizar_data(atual.get(campo, ""))
                else:
                    valor_esperado = limpar_valor(str(esperado.get(campo, "")))
                    valor_atual = limpar_valor(str(atual.get(campo, "")))
                if valor_esperado != valor_atual:
                    divergencias.append(
                        f"{documento}/{campo}: esperado={valor_esperado!r}, gravado={valor_atual!r}"
                    )

        if (
            ausentes
            or inesperadas
            or divergencias
            or len(linhas_depois) != len(esperados_por_documento)
        ):
            raise RuntimeError(
                "A LD foi fechada e reaberta, mas a consolidação não foi confirmada. "
                f"Esperados={len(esperados_por_documento)}; linhas={len(linhas_depois)}; "
                f"ausentes={len(ausentes)}; inesperados={len(inesperadas)}; "
                f"divergências={len(divergencias)}. "
                + (" | ".join(divergencias[:10]) if divergencias else "")
            )

        print(
            f"[INFO] LD consolidada na aba '{ABA_LD_LISTA_KM}': {len(linhas)} documento(s), "
            "sem duplicidade por documento e somente com PDFs da pasta oficial."
        )

        return {
            "ok": True,
            "linhas": len(linhas),
            "aba": ABA_LD_LISTA_KM,
            "planilha": str(PLANILHA_LD),
            "backup": backup_path,
        }

    except Exception:
        # Se falhar depois do backup, restaura para não deixar a LD em estado parcial.
        if arquivo_alterado:
            try:
                shutil.copy2(backup_path, str(PLANILHA_LD))
                print("[INFO] Backup da LD restaurado após falha na atualização KM.")
            except Exception as rb_err:
                print(f"[ERRO] Falha ao restaurar backup da LD: {rb_err}")
        raise

    finally:
        if wb is not None:
            try:
                wb.close()
            except Exception:
                pass


def processar():
    if not PASTA_PDFS.exists():
        print(f"[ERRO] Pasta não encontrada: {PASTA_PDFS}")
        return {
            "ok": False,
            "pdfs_lidos": 0,
            "linhas_gravadas": 0,
            "arquivo": str(PLANILHA_LD),
            "mensagem": f"Pasta não encontrada: {PASTA_PDFS}",
        }

    pdfs = sorted(PASTA_PDFS.glob("*.pdf"))
    if not pdfs:
        print(f"[AVISO] Nenhum PDF encontrado em: {PASTA_PDFS}")
        return {
            "ok": False,
            "pdfs_lidos": 0,
            "linhas_gravadas": 0,
            "arquivo": str(PLANILHA_LD),
            "mensagem": f"Nenhum PDF encontrado em: {PASTA_PDFS}",
        }

    caminhos_pdfs = {_caminho_normalizado(pdf) for pdf in pdfs}
    arquivos_pdf_oficiais = {str(pdf) for pdf in pdfs}
    registros_reparo = []
    registros_banco_fora_da_pasta = 0
    for obj in TransmittalKM.objects.all().iterator():
        dados_obj = dados_transmittal_model(obj)
        if not _registro_pertence_aos_pdfs_atuais(dados_obj, caminhos_pdfs):
            registros_banco_fora_da_pasta += 1
            continue
        # O banco funciona somente como fallback para PDFs oficiais que falhem
        # na leitura desta execução. A deduplicação posterior escolhe o mais recente.
        registros_reparo.append(dados_obj)

    wb, ws, ws_log = criar_planilha_nova()

    total_pdfs_lidos = 0
    total_registros = 0
    total_duplicados = 0
    # Registros que chegaram ao banco, mas não à LD, entram automaticamente
    # no lote de reparação mesmo que o PDF já esteja marcado como processado.
    registros_extraidos = list(registros_reparo)

    for pdf in pdfs:
        print(f"[INFO] Processando: {pdf.name}")
        texto = extrair_texto_pdf(pdf)

        if not texto.strip():
            registrar_log(
                ws_log,
                str(pdf),
                "",
                "ERRO",
                "Não foi possível extrair texto do PDF.",
            )
            continue

        total_pdfs_lidos += 1

        try:
            registros = extrair_registros_pdf(texto, pdf.name, pdf)
        except Exception as e:
            registrar_log(
                ws_log,
                str(pdf),
                "",
                "ERRO",
                f"Erro ao interpretar conteúdo: {e}",
            )
            continue

        registros_extraidos.extend(registros)

        for dados in registros:
            if dados.get("Status Parse", "OK") != "OK":
                registrar_log(
                    ws_log,
                    dados.get("Arquivo PDF", ""),
                    dados.get("Transmittal N°", ""),
                    dados.get("Status Parse", ""),
                    dados.get("Observação Parse", ""),
                )

    registros_latest, total_duplicados = filtrar_registros_latest_por_documento(registros_extraidos)
    versoes_por_documento = {}
    for dados in registros_extraidos:
        chave_doc = normalizar_documento_chave(dados.get("Documento", ""))
        if not chave_doc:
            continue
        versoes_por_documento.setdefault(chave_doc, set()).add((
            normalizar_data(dados.get("Data Envio", "")),
            limpar_valor(str(dados.get("Transmittal N°", ""))).upper(),
        ))
    historicos_distintos = sum(max(0, len(versoes) - 1) for versoes in versoes_por_documento.values())

    if registros_banco_fora_da_pasta:
        registrar_log(
            ws_log,
            str(PASTA_PDFS),
            "",
            "AVISO",
            f"{registros_banco_fora_da_pasta} registro(s) histórico(s) do banco apontam para PDFs "
            "fora da pasta oficial ou ausentes. Eles foram ignorados e não foram apagados.",
        )
        print(
            f"[AVISO] {registros_banco_fora_da_pasta} registro(s) do banco fora da pasta oficial "
            "foram ignorados e preservados no banco."
        )

    if total_duplicados:
        registrar_log(
            ws_log,
            str(PASTA_PDFS),
            "",
            "INFO",
            f"{total_duplicados} candidato(s) repetido(s) comparado(s), incluindo o fallback de segurança "
            f"do banco; {historicos_distintos} versão(ões) histórica(s) realmente distinta(s). "
            "Mantida uma linha por documento, priorizando Data Envio e depois o maior Transmittal.",
        )

    if registros_latest:
        resultado_ld = atualizar_lista_km_dentro_ld(registros_latest)
    else:
        resultado_ld = {
            "ok": True,
            "linhas": 0,
            "aba": ABA_LD_LISTA_KM,
            "planilha": str(PLANILHA_LD),
            "backup": "",
            "mensagem": "Nenhum transmittal novo encontrado; a LD não foi alterada.",
        }

    # O banco só passa a marcar novos PDFs como processados depois que a LD
    # confirmou a gravação. Isso mantém a execução autorreparável.
    for dados in registros_latest:
        salvar_no_banco(dados, arquivos_pdf_oficiais=arquivos_pdf_oficiais)

    total_registros = int(resultado_ld.get("linhas") or 0)
    wb.close()

    print("\n=== RESUMO TRANSMITTAL KM ===")
    print(f"PDFs lidos: {total_pdfs_lidos}")
    print(f"Linhas gravadas: {total_registros}")
    print(f"Duplicados ignorados por documento: {total_duplicados}")
    print(f"LD atualizada: {resultado_ld.get('planilha')} | Aba: {resultado_ld.get('aba')}")

    return {
        "ok": True,
        "pdfs_lidos": total_pdfs_lidos,
        "linhas_gravadas": total_registros,
        "duplicados_ignorados": total_duplicados,
        "registros_banco_fora_da_pasta": registros_banco_fora_da_pasta,
        "arquivo": str(PLANILHA_LD),
        "ld_master": resultado_ld,
        "quantidade_processada": total_registros,
        "detalhes": {
            "pdfs_lidos": total_pdfs_lidos,
            "linhas_gravadas": total_registros,
            "duplicados_ignorados": total_duplicados,
            "registros_banco_fora_da_pasta": registros_banco_fora_da_pasta,
            "arquivo": str(PLANILHA_LD),
            "ld_master": resultado_ld,
        },
    }



def executar():
    global pdfplumber

    try:
        import pdfplumber as pdfplumber_module
        pdfplumber = pdfplumber_module

        resumo = processar()
        if not isinstance(resumo, dict):
            return {
                "ok": False,
                "mensagem": "Transmittal KM não retornou resumo de processamento.",
                "detalhes": {"resumo": str(resumo)},
            }

        ok = bool(resumo.get("ok", True))
        pdfs_lidos = int(resumo.get("pdfs_lidos") or 0)
        linhas_gravadas = int(resumo.get("linhas_gravadas") or 0)
        arquivo = resumo.get("arquivo") or str(PLANILHA_LD)

        if not ok:
            return {
                "ok": False,
                "mensagem": resumo.get("mensagem") or "Transmittal KM não foi concluído.",
                "quantidade_processada": linhas_gravadas,
                "detalhes": resumo,
            }

        arquivos_pdf_oficiais = [str(pdf) for pdf in PASTA_PDFS.glob("*.pdf")]
        resultado_vinculo = executar_vinculo_km_ld(
            arquivos_pdf_permitidos=arquivos_pdf_oficiais
        )
        detalhes_vinculo = resultado_vinculo.get("detalhes", {}) if isinstance(resultado_vinculo, dict) else {}

        vinculados_auto = int(detalhes_vinculo.get("vinculados_auto") or 0)
        pendentes = int(detalhes_vinculo.get("pendentes") or 0)
        sem_match = int(detalhes_vinculo.get("sem_match") or 0)
        multiplos = int(detalhes_vinculo.get("multiplos") or 0)
        conflitos = int(detalhes_vinculo.get("conflitos") or 0)

        return {
            "ok": True,
            "mensagem": (
                "Transmittal KM executado com sucesso. "
                f"PDFs lidos: {pdfs_lidos}. "
                f"Linhas gravadas: {linhas_gravadas}. "
                f"Vínculos automáticos: {vinculados_auto}. "
                f"Pendentes: {pendentes}. "
                f"Sem match: {sem_match}."
            ),
            "quantidade_processada": linhas_gravadas,
            "detalhes": {
                "pdfs_lidos": pdfs_lidos,
                "linhas_gravadas": linhas_gravadas,
                "arquivo": arquivo,
                "vinculo_km_ld": {
                    "ok": bool(resultado_vinculo.get("ok", False)) if isinstance(resultado_vinculo, dict) else False,
                    "mensagem": resultado_vinculo.get("mensagem", "") if isinstance(resultado_vinculo, dict) else "",
                    "vinculados_auto": vinculados_auto,
                    "pendentes": pendentes,
                    "sem_match": sem_match,
                    "multiplos": multiplos,
                    "conflitos": conflitos,
                    "detalhes": detalhes_vinculo,
                },
            },
        }

    except Exception as e:
        print(f"[ERRO TRANSMITTAL KM] {e}")
        return {
            "ok": False,
            "mensagem": f"Erro no Transmittal KM: {e}",
            "detalhes": {"erro": str(e), "tipo": e.__class__.__name__},
        }
