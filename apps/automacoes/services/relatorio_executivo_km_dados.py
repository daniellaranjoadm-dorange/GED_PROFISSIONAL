import json, os, re, sys
from collections import Counter, defaultdict
from datetime import date, datetime
from pathlib import Path

sys.path.insert(0, r"D:\GED_PROFISSIONAL")
import xlwings as xw

PLANILHA = r"\\virm-rgr022\FILESERVER\Projetos\05_HANDYMAX\09. Doc Control\3 - LD\I-LD-4880.00-9311-000-CZ1-001_RD.xlsm"
SAIDA = Path(os.environ.get("RELATORIO_EXECUTIVO_DADOS", Path(__file__).with_name("dados_relatorio_direcao.json")))
HOJE = date.today()
INVALIDOS = {"", "N/A", "NA", "NOTAPPLICABLE", "NOT APPLICABLE", "TBD", "-", "CANCELADO"}

def texto(v):
    if v is None: return ""
    if isinstance(v, float) and v.is_integer(): return str(int(v))
    return re.sub(r"\s+", " ", str(v).strip())

def chave(v): return re.sub(r"\s+", "", texto(v).upper())
def valido(v): return chave(v) not in {re.sub(r"\s+", "", x) for x in INVALIDOS}

def data_val(v):
    if isinstance(v, datetime): return v.date()
    if isinstance(v, date): return v
    for fmt in ("%d/%m/%Y", "%d.%m.%Y", "%d-%m-%Y", "%Y-%m-%d"):
        try: return datetime.strptime(texto(v), fmt).date()
        except ValueError: pass
    return None

def trans_key(v): return tuple(int(x) for x in re.findall(r"\d+", texto(v))) or (0,)
def faixa(d):
    if d <= 7: return "0-7 dias"
    if d <= 15: return "8-15 dias"
    if d <= 30: return "16-30 dias"
    if d <= 60: return "31-60 dias"
    if d <= 90: return "61-90 dias"
    return ">90 dias"
def prioridade(d):
    if d > 90: return "CRÍTICA"
    if d > 60: return "ALTA"
    if d > 30: return "MÉDIA"
    return "NORMAL"
def tipo_especial(toc, titulo):
    s = f"{texto(toc)} {texto(titulo)}".upper()
    if "ARMATURE" in s: return "ARMATURE LIST"
    if "ETS" in s or "EQUIPMENT TECHNICAL SPESIFICATION" in s or "EQUIPMENT TECHNICAL SPECIFICATION" in s: return "ETS"
    return "DOCUMENTO TÉCNICO"

app = xw.App(visible=False, add_book=False)
app.display_alerts = False
wb = None
try:
    wb = app.books.open(PLANILHA, update_links=False, read_only=True, ignore_read_only_recommended=True)
    gl, ld = wb.sheets["GENERAL LIST KM"], wb.sheets["LD PROJETO BASICO"]
    last_gl = max(gl.range(f"{c}{gl.cells.last_cell.row}").end("up").row for c in ("C","F","O","P","S","W"))
    raw_gl = gl.range(f"A2:W{last_gl}").value or []
    if raw_gl and not isinstance(raw_gl[0], list): raw_gl = [raw_gl]
    todos_gl = []
    recebidos = []
    for linha, v in enumerate(raw_gl, start=2):
        if not texto(v[2]): continue
        item = {"linha_gl": linha, "fase": texto(v[0]), "toc": texto(v[1]), "km": texto(v[2]), "km_key": chave(v[2]),
                "titulo": texto(v[3]), "disciplina": texto(v[4]), "customer": texto(v[5]), "customer_key": chave(v[5]),
                "transmittal": texto(v[14]), "data": data_val(v[15]), "tipo": tipo_especial(v[1], v[3]),
                "bv_posted": data_val(v[18]), "bv_status": texto(v[19]), "bv_since": data_val(v[20]), "bv_action": texto(v[21]), "bv_pending": texto(v[22])}
        todos_gl.append(item)
        if item["transmittal"] and item["data"]: recebidos.append(item)

    latest = {}
    for x in recebidos:
        crit = (x["data"], trans_key(x["transmittal"]), x["linha_gl"])
        if x["km_key"] not in latest or crit > latest[x["km_key"]][0]: latest[x["km_key"]] = (crit, x)
    fontes = [x[1] for x in latest.values()]

    last_ld = max(ld.range(f"{c}{ld.cells.last_cell.row}").end("up").row for c in ("B","C","H","N","V","Y","AB","AH"))
    raw_ld = ld.range(f"A2:AH{last_ld}").value or []
    if raw_ld and not isinstance(raw_ld[0], list): raw_ld = [raw_ld]
    itens_ld, por_b, por_c, por_h = [], defaultdict(list), defaultdict(list), defaultdict(list)
    for linha, v in enumerate(raw_ld, start=2):
        x = {"linha_ld": linha, "tipo_ld": texto(v[0]), "dox": texto(v[1]), "tp": texto(v[2]), "revisao": texto(v[3]),
             "titulo_ld": texto(v[4]), "disciplina_ld": texto(v[6]) if valido(v[6]) else texto(v[5]), "km_ld": texto(v[7]), "transmittal_ld": texto(v[9]),
             "data_ld": texto(v[10]), "km_emitido": texto(v[11]), "status": texto(v[12]), "status_emissao": texto(v[13]),
             "resp_issue": texto(v[21]), "pcf_num":texto(v[24]), "pcf_data":data_val(v[25]), "pcf_status":texto(v[26]),
             "pcf_respondida":texto(v[27]), "pcf_data_resposta":data_val(v[28]), "pcf_grd_resposta":texto(v[29]),
             "pcf_qtd":texto(v[30]), "pcf_abertos":texto(v[31]), "pcf_revisao":texto(v[32]), "pcf_final":texto(v[33])}
        itens_ld.append(x)
        if chave(x["dox"]): por_b[chave(x["dox"])].append(x)
        if chave(x["tp"]): por_c[chave(x["tp"])].append(x)
        if chave(x["km_ld"]): por_h[chave(x["km_ld"])].append(x)

    base = []
    for src in fontes:
        matches, vistos, tipos = [], set(), []
        for nome, grupo in (("KM GENERAL ↔ LD H", por_h.get(src["km_key"], [])),
                            ("CUSTOMER GENERAL ↔ LD B", por_b.get(src["customer_key"], []) if src["customer_key"] else []),
                            ("CUSTOMER GENERAL ↔ LD C", por_c.get(src["customer_key"], []) if src["customer_key"] else [])):
            if grupo: tipos.append(nome)
            for x in grupo:
                if x["linha_ld"] not in vistos: vistos.add(x["linha_ld"]); matches.append(x)
        tp_validos = sorted({x["tp"] for x in matches if valido(x["tp"])})
        emitido = any(chave(x["status_emissao"]) == "EMITIDO" for x in matches)
        idade = max(0, (HOJE - src["data"]).days)
        status_ld = " / ".join(sorted({x["status_emissao"] for x in matches if x["status_emissao"]}))
        base.append({
            "tipo": src["tipo"], "km": src["km"], "titulo": src["titulo"], "disciplina": src["disciplina"],
            "customer": src["customer"], "transmittal": src["transmittal"], "data": src["data"].isoformat(),
            "dias": idade, "faixa": faixa(idade), "prioridade": prioridade(idade), "correlacao": " + ".join(tipos),
            "tp": " / ".join(tp_validos), "dox": " / ".join(sorted({x["dox"] for x in matches if valido(x["dox"])})),
            "status_emissao": status_ld, "emitido": "SIM" if emitido else "NÃO", "linhas_ld": ", ".join(str(x["linha_ld"]) for x in matches),
            "linha_gl": src["linha_gl"], "fase": src["fase"], "toc": src["toc"]
        })

    ets = [x for x in base if x["tipo"] == "ETS" and x["correlacao"] and x["emitido"] == "NÃO"]
    armature = [x for x in base if x["tipo"] == "ARMATURE LIST" and x["correlacao"] and x["emitido"] == "NÃO"]
    corr_pend = [x for x in base if x["tipo"] == "DOCUMENTO TÉCNICO" and x["tp"] and x["emitido"] == "NÃO"]
    sem_corr = [x for x in base if not x["tp"] and (x["tipo"] == "DOCUMENTO TÉCNICO" or not x["correlacao"])]

    # Uma linha executiva por número Transpetro. Um mesmo TP pode consolidar vários documentos KM.
    grupos_tp = defaultdict(list)
    for x in corr_pend:
        for numero_tp in [p.strip() for p in x["tp"].split(" / ") if p.strip()]: grupos_tp[chave(numero_tp)].append((numero_tp, x))
    corr_agrupados = []
    for grupo in grupos_tp.values():
        numero_tp = grupo[0][0]; itens = [g[1] for g in grupo]
        datas = [data_val(x["data"]) for x in itens if data_val(x["data"])]
        primeira, ultima = min(datas), max(datas)
        dias = max(0, (HOJE - primeira).days)
        corr_agrupados.append({
            "tp": numero_tp, "qtd_km": len({x["km"] for x in itens}), "kms": " | ".join(sorted({x["km"] for x in itens})),
            "titulos": " | ".join(sorted({x["titulo"] for x in itens})), "disciplinas": " / ".join(sorted({x["disciplina"] for x in itens if x["disciplina"]})),
            "customers": " | ".join(sorted({x["customer"] for x in itens if x["customer"]})), "transmittals": " / ".join(sorted({x["transmittal"] for x in itens if x["transmittal"]}, key=trans_key)),
            "primeira_data": primeira.isoformat(), "ultima_data": ultima.isoformat(), "dias": dias, "faixa": faixa(dias), "prioridade": prioridade(dias),
            "status_emissao": " / ".join(sorted({x["status_emissao"] for x in itens if x["status_emissao"]})),
            "linhas_ld": ", ".join(sorted({x["linhas_ld"] for x in itens if x["linhas_ld"]})), "qtd_linhas_general": len(itens)
        })

    # Reconciliação de universos: escopo da LD não é igual ao subconjunto recebido e pendente.
    ld_ets = [x for x in itens_ld if chave(x["tp"]) == "NOTAPPLICABLE" and chave(x["tipo_ld"]) == "ET"]
    ld_arm = [x for x in itens_ld if chave(x["tp"]) == "NOTAPPLICABLE" and chave(x["tipo_ld"]) == "LI"]
    gl_ets_total = [x for x in todos_gl if x["tipo"] == "ETS"]
    gl_arm_total = [x for x in todos_gl if x["tipo"] == "ARMATURE LIST"]
    gl_tbd = [x for x in todos_gl if chave(x["customer"]) == "TBD"]
    gl_tbd_latest = {}
    for x in gl_tbd:
        crit = (1 if x["data"] and x["transmittal"] else 0, x["data"] or date.min, trans_key(x["transmittal"]), x["linha_gl"])
        if x["km_key"] not in gl_tbd_latest or crit > gl_tbd_latest[x["km_key"]][0]: gl_tbd_latest[x["km_key"]] = (crit, x)
    tbd_detalhe = []
    for _, x in gl_tbd_latest.values():
        recebido = bool(x["data"] and x["transmittal"]); dias = max(0, (HOJE-x["data"]).days) if recebido else None
        tbd_detalhe.append({"km":x["km"],"titulo":x["titulo"],"disciplina":x["disciplina"],"customer":x["customer"],"transmittal":x["transmittal"],
            "data":x["data"].isoformat() if x["data"] else "","recebido":"SIM" if recebido else "NÃO","dias":dias,"prioridade":prioridade(dias) if dias is not None else "ALTA — DEFINIÇÃO PENDENTE","linha_gl":x["linha_gl"],"toc":x["toc"]})

    recebidos_por_km = {x["km_key"]: x for x in fontes}
    def montar_escopo_especial(linhas, tipo_nome):
        saida = []
        for x in linhas:
            src = recebidos_por_km.get(chave(x["km_ld"]))
            recebido = src is not None
            emitido = chave(x["status_emissao"]) == "EMITIDO"
            dias = max(0, (HOJE-src["data"]).days) if recebido else None
            situacao = "EMITIDO" if emitido else ("RECEBIDO E NÃO EMITIDO" if recebido else "NÃO RECEBIDO DA KM")
            saida.append({"tipo":tipo_nome,"km":x["km_ld"],"titulo":x["titulo_ld"],"dox":x["dox"],"disciplina":x["disciplina_ld"],
                "transmittal":src["transmittal"] if src else x["transmittal_ld"],"data":src["data"].isoformat() if src else "","dias":dias,
                "prioridade":prioridade(dias) if dias is not None and not emitido else ("CONCLUÍDO" if emitido else "ALTA — NÃO RECEBIDO"),
                "status":x["status"],"status_emissao":x["status_emissao"],"situacao":situacao,"linha_ld":x["linha_ld"],"linha_gl":src["linha_gl"] if src else ""})
        return sorted(saida,key=lambda z:({"RECEBIDO E NÃO EMITIDO":0,"NÃO RECEBIDO DA KM":1,"EMITIDO":2}[z["situacao"]],-(z["dias"] or 0),z["km"]))
    escopo_ets = montar_escopo_especial(ld_ets,"ETS")
    escopo_arm = montar_escopo_especial(ld_arm,"ARMATURE LIST")

    gl_km = {x["km_key"] for x in todos_gl if x["km_key"]}
    gl_customer = {x["customer_key"] for x in todos_gl if x["customer_key"]}
    faltantes = {}
    for x in itens_ld:
        if chave(x["resp_issue"]) != "KONGSBERG" or not valido(x["tp"]): continue
        relacionado = chave(x["tp"]) in gl_customer or chave(x["dox"]) in gl_customer or chave(x["km_ld"]) in gl_km
        if relacionado: continue
        k = chave(x["tp"])
        if k not in faltantes: faltantes[k] = {"tp": x["tp"], "dox": x["dox"], "revisao": x["revisao"], "titulo": x["titulo_ld"],
            "disciplina": x["disciplina_ld"], "status": x["status"], "status_emissao": x["status_emissao"], "resp_issue": x["resp_issue"], "linha_ld": x["linha_ld"]}

    # PCFs emitidas/recebidas sem documento de resposta: uma linha por PCF, consolidando repetições da LD.
    pcf_grupos = defaultdict(list)
    for x in itens_ld:
        if valido(x["pcf_num"]) and not valido(x["pcf_respondida"]): pcf_grupos[chave(x["pcf_num"])].append(x)
    pcf_abertas = []
    def numero(v):
        try: return int(float(texto(v)))
        except: return 0
    for grupo in pcf_grupos.values():
        x = grupo[0]; datas=[g["pcf_data"] for g in grupo if g["pcf_data"]]; inicio=min(datas) if datas else None
        dias=max(0,(HOJE-inicio).days) if inicio else None
        pcf_abertas.append({"pcf":x["pcf_num"],"tp":" / ".join(sorted({g["tp"] for g in grupo if valido(g["tp"])})),"dox":" / ".join(sorted({g["dox"] for g in grupo if g["dox"]})),
            "revisao":" / ".join(sorted({g["revisao"] for g in grupo if g["revisao"]})),"titulo":x["titulo_ld"],"disciplina":x["disciplina_ld"],"responsavel":x["resp_issue"],
            "data":inicio.isoformat() if inicio else "","dias":dias,"faixa":faixa(dias) if dias is not None else "SEM DATA","prioridade":prioridade(dias) if dias is not None else "ALTA — SEM DATA",
            "status_pcf":" / ".join(sorted({g["pcf_status"] for g in grupo if g["pcf_status"]})),"qtd_comentarios":max(numero(g["pcf_qtd"]) for g in grupo),
            "comentarios_abertos":max(numero(g["pcf_abertos"]) for g in grupo),"em_revisao":max(numero(g["pcf_revisao"]) for g in grupo),
            "status_final":" / ".join(sorted({g["pcf_final"] for g in grupo if g["pcf_final"]})),"linhas_ld":", ".join(str(g["linha_ld"]) for g in grupo)})

    # Documentos da GENERAL LIST publicados no BV: uma linha por Nº KM, mantendo a postagem mais recente.
    bv_latest = {}
    for x in todos_gl:
        if not x["bv_posted"]: continue
        crit=(x["bv_posted"],x["bv_since"] or date.min,x["linha_gl"])
        if x["km_key"] not in bv_latest or crit>bv_latest[x["km_key"]][0]: bv_latest[x["km_key"]]=(crit,x)
    docs_bv=[]
    for _,x in bv_latest.values():
        dias=max(0,(HOJE-(x["bv_since"] or x["bv_posted"])).days)
        docs_bv.append({"km":x["km"],"titulo":x["titulo"],"disciplina":x["disciplina"],"customer":x["customer"],"transmittal":x["transmittal"],
            "posted":x["bv_posted"].isoformat(),"status":x["bv_status"],"since":(x["bv_since"] or x["bv_posted"]).isoformat(),"action":x["bv_action"],"pending":numero(x["bv_pending"]),
            "dias":dias,"prioridade":"CRÍTICA" if numero(x["bv_pending"])>0 and dias>30 else ("ALTA" if numero(x["bv_pending"])>0 else "NORMAL"),"linha_gl":x["linha_gl"]})

    # Matriz executiva por responsável e STATUS da LD, sempre com Nº Transpetro distinto.
    matriz_sets=defaultdict(set)
    for x in itens_ld:
        if not valido(x["tp"]): continue
        resp=texto(x["resp_issue"]) or "SEM RESPONSÁVEL"; status=texto(x["status"]) or "SEM STATUS"
        matriz_sets[(resp,status)].add(chave(x["tp"]))
    matriz_status=[{"responsavel":r,"status":s,"qtd_tp":len(v)} for (r,s),v in matriz_sets.items()]
    matriz_status.sort(key=lambda x:(x["responsavel"],x["status"]))

    ordenar = lambda xs: sorted(xs, key=lambda x: (-x.get("dias",0), x.get("km", x.get("tp",""))))
    resumo = {
        "data_referencia": HOJE.isoformat(), "arquivo_fonte": PLANILHA, "recebidos_unicos": len(base),
        "emitidos": sum(x["emitido"] == "SIM" for x in base), "ets_pendentes": len(ets), "armature_pendentes": len(armature),
        "correlacionados_pendentes": len(corr_pend), "tp_unicos_pendentes": len(corr_agrupados), "sem_correlacao_tp": len(sem_corr), "ld_kongsberg_sem_general": len(faltantes),
        "criticos": sum(x["prioridade"] == "CRÍTICA" for x in ets + armature + corr_pend + sem_corr),
        "disciplinas_pendentes": dict(Counter(x["disciplina"] or "SEM DISCIPLINA" for x in ets + armature + corr_pend)),
        "faixas_pendentes": dict(Counter(x["faixa"] for x in ets + armature + corr_pend)),
        "duplicidades_consolidadas": len(recebidos) - len(base),
        "ld_ets_linhas": len(ld_ets), "ld_ets_dox_unicos": len({chave(x["dox"]) for x in ld_ets}), "general_ets_total": len({x["km_key"] for x in gl_ets_total}), "general_ets_recebidas": sum(x["tipo"]=="ETS" for x in base), "general_ets_pendentes": len(ets), "ld_ets_recebidas_pendentes":sum(x["situacao"]=="RECEBIDO E NÃO EMITIDO" for x in escopo_ets), "ld_ets_nao_recebidas":sum(x["situacao"]=="NÃO RECEBIDO DA KM" for x in escopo_ets), "ld_ets_emitidas":sum(x["situacao"]=="EMITIDO" for x in escopo_ets),
        "ld_armature_linhas": len(ld_arm), "ld_armature_dox_unicos": len({chave(x["dox"]) for x in ld_arm}), "general_armature_total": len({x["km_key"] for x in gl_arm_total}), "general_armature_recebidas": sum(x["tipo"]=="ARMATURE LIST" for x in base), "general_armature_pendentes": len(armature), "ld_armature_recebidas_pendentes":sum(x["situacao"]=="RECEBIDO E NÃO EMITIDO" for x in escopo_arm), "ld_armature_nao_recebidas":sum(x["situacao"]=="NÃO RECEBIDO DA KM" for x in escopo_arm), "ld_armature_emitidas":sum(x["situacao"]=="EMITIDO" for x in escopo_arm),
        "general_tbd_linhas": len(gl_tbd), "general_tbd_unicos": len(tbd_detalhe), "general_tbd_recebidos": sum(x["recebido"]=="SIM" for x in tbd_detalhe), "general_tbd_nao_recebidos": sum(x["recebido"]=="NÃO" for x in tbd_detalhe),
        "pcf_abertas_unicas":len(pcf_abertas), "pcf_criticas":sum(x["prioridade"]=="CRÍTICA" for x in pcf_abertas), "pcf_com_comentarios_abertos":sum(x["comentarios_abertos"]>0 for x in pcf_abertas),
        "bv_documentos_unicos":len(docs_bv), "bv_com_pendencias":sum(x["pending"]>0 for x in docs_bv), "bv_pendencias_total":sum(x["pending"] for x in docs_bv),
        "tp_distintos_resumo":len({tp for v in matriz_sets.values() for tp in v})
    }
    payload = {"resumo": resumo, "base": ordenar(base), "ets": ordenar(ets), "armature": ordenar(armature),
               "correlacionados_pendentes": ordenar(corr_pend), "correlacionados_tp_agrupados": sorted(corr_agrupados,key=lambda x:(-x["dias"],x["tp"])), "sem_correlacao": ordenar(sem_corr), "tbd_detalhe": sorted(tbd_detalhe,key=lambda x:(x["recebido"],x["km"])), "escopo_ets":escopo_ets, "escopo_armature":escopo_arm,
               "ld_kongsberg_sem_general": sorted(faltantes.values(), key=lambda x: (x["disciplina"], x["tp"])),
               "pcf_abertas":sorted(pcf_abertas,key=lambda x:(-(x["dias"] or -1),x["pcf"])), "documentos_bv":sorted(docs_bv,key=lambda x:(-x["pending"],-x["dias"],x["km"])), "matriz_status":matriz_status}
    SAIDA.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
finally:
    if wb is not None: wb.close()
    app.quit()
