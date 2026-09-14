from reportlab.pdfgen import canvas
from reportlab.lib.pagesizes import A4, landscape
from reportlab.lib.colors import HexColor, white
from reportlab.lib.units import mm
from reportlab.platypus import Table, TableStyle, Paragraph
from reportlab.lib.styles import ParagraphStyle
from reportlab.pdfbase.pdfmetrics import stringWidth
from pypdf import PdfReader
from pathlib import Path

OUT = Path(r"D:\GED_PROFISSIONAL\outputs\pacote_diretoria_r12_enterprise\RELATORIO_EXECUTIVO_GESTAO_INTEGRADA_R12_ENTERPRISE.pdf")
W, H = landscape(A4)
NAVY, TEAL, CYAN, ORANGE = map(HexColor, ["#17365D", "#0F6B78", "#35C7E8", "#F7931E"])
INK, MUTED, LIGHT, GREEN, AMBER, RED = map(HexColor, ["#17324D", "#657C8C", "#DCE6F1", "#E2F0D9", "#FFF2CC", "#FCE4D6"])
c = canvas.Canvas(str(OUT), pagesize=(W,H))

def footer(page):
    c.setFillColor(MUTED); c.setFont("Helvetica", 8)
    c.drawString(18*mm, 9*mm, "D'OR@NGE | Gestao Integrada de Document Control | R12 Enterprise | 20/08/2026")
    c.drawRightString(W-18*mm, 9*mm, f"Pagina {page}")

def header(title, kicker, page):
    c.setFillColor(NAVY); c.rect(0,H-28*mm,W,28*mm,fill=1,stroke=0)
    c.setFillColor(ORANGE); c.setFont("Helvetica-Bold",9); c.drawString(18*mm,H-10*mm,kicker)
    c.setFillColor(white); c.setFont("Helvetica-Bold",20); c.drawString(18*mm,H-21*mm,title)
    footer(page)

def wrap(text, x, y, width, size=11, leading=15, color=INK, bold=False):
    font="Helvetica-Bold" if bold else "Helvetica"; c.setFont(font,size); c.setFillColor(color)
    words=text.split(); line=""; yy=y
    for word in words:
        trial=(line+" "+word).strip()
        if stringWidth(trial,font,size)>width and line:
            c.drawString(x,yy,line); yy-=leading; line=word
        else: line=trial
    if line: c.drawString(x,yy,line); yy-=leading
    return yy

def card(x,y,w,h,label,value,sub,color):
    c.setFillColor(HexColor("#F7FAFC")); c.roundRect(x,y,w,h,5,fill=1,stroke=0)
    c.setStrokeColor(color); c.setLineWidth(1.2); c.roundRect(x,y,w,h,5,fill=0,stroke=1)
    c.setFillColor(MUTED); c.setFont("Helvetica-Bold",8); c.drawString(x+8,y+h-14,label.upper())
    c.setFillColor(color); c.setFont("Helvetica-Bold",17); c.drawString(x+8,y+h-37,value)
    c.setFillColor(MUTED); c.setFont("Helvetica",8); c.drawString(x+8,y+9,sub)

# 1
header("Gestao Integrada de Document Control", "RELATORIO EXECUTIVO PARA DIRETORIA", 1)
c.setFillColor(INK); c.setFont("Helvetica-Bold",30); c.drawString(18*mm,H-55*mm,"A separacao organiza o trabalho,")
c.drawString(18*mm,H-69*mm,"mas ainda nao entrega a reducao de 20%.")
c.setFillColor(TEAL); c.roundRect(18*mm,H-126*mm,W-36*mm,35*mm,6,fill=1,stroke=0)
c.setFillColor(white); c.setFont("Helvetica-Bold",15); c.drawString(26*mm,H-106*mm,"Mensagem central")
wrap("Os custos do Doc Control e do Arquivo Tecnico devem ser avaliados de forma consolidada. Transferir pessoas entre setores nao constitui economia.",26*mm,H-116*mm,W-52*mm,12,16,white)
c.setFillColor(MUTED); c.setFont("Helvetica",10); c.drawString(18*mm,30*mm,"Portifolio: Handy Size + Gaseiros/GLP + Mid Range/MR1")
c.showPage()

# 2
header("Diagnostico consolidado", "01 | VISAO EXECUTIVA", 2)
xs=[18,70,122,174,226]; vals=[("Custo acordado","R$ 7,290 mi","baseline",CYAN),("Custo separado","R$ 7,291 mi","DC + Arquivo",ORANGE),("Reducao real","aprox. 0,0%","meta >= 20%",HexColor("#C00000")),("HM separado","1.113,5","+85 HM",ORANGE),("Gap p/ meta","R$ 1,459 mi","reducao adicional",HexColor("#C00000"))]
for x,v in zip(xs,vals): card(x*mm,H-78*mm,46*mm,34*mm,*v)
c.setFillColor(AMBER); c.roundRect(18*mm,H-134*mm,W-36*mm,38*mm,5,fill=1,stroke=0)
wrap("A reducao de 49,7% observada isoladamente no Doc Control reaparece no Arquivo Tecnico. O custo total fica praticamente igual ao acordado.",25*mm,H-111*mm,W-50*mm,14,19,INK,True)
c.setFillColor(INK); c.setFont("Helvetica-Bold",13); c.drawString(18*mm,35*mm,"Meta financeira: custo-alvo maximo de R$ 5,832 milhoes.")
c.showPage()

# 3
header("Escopo e alocacao estao desalinhados", "02 | ESCOPO E HM", 3)
c.setFillColor(LIGHT); c.roundRect(18*mm,H-135*mm,166*mm,88*mm,5,fill=1,stroke=0)
c.setFillColor(CYAN); c.setFont("Helvetica-Bold",28); c.drawString(26*mm,H-65*mm,"aprox. 90%")
c.setFillColor(INK); c.setFont("Helvetica-Bold",15); c.drawString(26*mm,H-78*mm,"DOC CONTROL")
wrap("Governanca documental; GED e rastreabilidade; revisoes e prazos; indicadores; auditorias; conformidade; interfaces; gestao do ciclo documental.",26*mm,H-90*mm,145*mm,11,15,INK)
c.setFillColor(AMBER); c.roundRect(192*mm,H-135*mm,87*mm,88*mm,5,fill=1,stroke=0)
c.setFillColor(ORANGE); c.setFont("Helvetica-Bold",28); c.drawString(200*mm,H-65*mm,"aprox. 10%")
c.setFillColor(INK); c.setFont("Helvetica-Bold",15); c.drawString(200*mm,H-78*mm,"ARQUIVO TECNICO")
wrap("Impressao; carimbos; distribuicao fisica; recolhimento; guarda fisica.",200*mm,H-90*mm,70*mm,11,15,INK)
c.setFillColor(INK); c.setFont("Helvetica-Bold",13); c.drawString(18*mm,39*mm,"HM: Doc Control 429,5 (38,6%) | Arquivo Tecnico 684,0 (61,4%)")
c.setFillColor(MUTED); c.setFont("Helvetica",9); c.drawString(18*mm,29*mm,"Os percentuais de escopo sao premissas gerenciais informadas e devem ser validados pela Diretoria.")
c.showPage()

# 4
header("Comparativo por projeto", "03 | ESTRUTURA", 4)
style=ParagraphStyle('cell',fontName='Helvetica',fontSize=9,leading=11,textColor=INK)
data_tbl=[["Projeto","HM acordado","HM Doc Control","HM Arquivo","HM combinado","Variacao"],["Handy Size","245,0","157,0","143,0","300,0","+55,0"],["Gaseiros / GLP","444,5","145,5","276,0","421,5","-23,0"],["Mid Range / MR1","339,0","127,0","265,0","392,0","+53,0"],["TOTAL","1.028,5","429,5","684,0","1.113,5","+85,0"]]
t=Table(data_tbl,colWidths=[48*mm,34*mm,34*mm,34*mm,34*mm,30*mm],rowHeights=12*mm)
t.setStyle(TableStyle([('BACKGROUND',(0,0),(-1,0),NAVY),('TEXTCOLOR',(0,0),(-1,0),white),('FONTNAME',(0,0),(-1,0),'Helvetica-Bold'),('ALIGN',(1,0),(-1,-1),'RIGHT'),('FONTNAME',(0,-1),(-1,-1),'Helvetica-Bold'),('BACKGROUND',(0,-1),(-1,-1),GREEN),('GRID',(0,0),(-1,-1),0.5,HexColor('#AABCCC')),('FONTNAME',(0,1),(-1,-2),'Helvetica'),('FONTSIZE',(0,0),(-1,-1),9),('VALIGN',(0,0),(-1,-1),'MIDDLE')]))
t.wrapOn(c,W,H); t.drawOn(c,18*mm,H-118*mm)
c.setFillColor(AMBER); c.roundRect(18*mm,28*mm,W-36*mm,28*mm,5,fill=1,stroke=0)
wrap("Handy Size e Mid Range/MR1 crescem; a reducao de Gaseiros/GLP nao compensa o saldo global de +85 HM.",25*mm,45*mm,W-50*mm,12,16,INK,True)
c.showPage()

# 5
header("Gestao PJ custa menos que cada supervisao local", "04 | COST BENCHMARK", 5)
card(18*mm,H-82*mm,58*mm,34*mm,"Gestao atual - PJ","R$ 11.000","governanca transversal",TEAL)
card(84*mm,H-82*mm,58*mm,34*mm,"Supervisor Niteroi","R$ 11.850","PJ: R$ 850/mes menor",CYAN)
card(150*mm,H-82*mm,58*mm,34*mm,"Supervisor GLP / RG","R$ 14.670","PJ: R$ 3.670/mes menor",ORANGE)
card(216*mm,H-82*mm,63*mm,34*mm,"Duas supervisoes","R$ 26.520","PJ: R$ 15.520/mes menor",HexColor("#C00000"))
c.setFillColor(AMBER); c.roundRect(18*mm,H-137*mm,W-36*mm,38*mm,5,fill=1,stroke=0)
wrap("A Gestao PJ custa 7,2% menos que Niteroi, 25,0% menos que GLP/RG e 58,5% menos que as duas supervisoes somadas. A diferenca conjunta equivale a R$ 186,2 mil por ano.",25*mm,H-113*mm,W-50*mm,13,18,INK,True)
wrap("Benchmark financeiro; nao implica equivalencia automatica de cargos. O enquadramento deve refletir escopo, abrangencia e responsabilidade consolidada.",18*mm,34*mm,W-36*mm,10,14,MUTED)
c.showPage()

# 6
header("Decisao recomendada", "05 | ENCAMINHAMENTO", 6)
items=[("1","Formalizar setores","Fronteiras claras entre governanca documental e operacao fisica."),("2","Consolidar indicadores","HM, HH e custos sempre apresentados como Doc Control + Arquivo Tecnico."),("3","Recalibrar capacidade","Eliminar o gap de R$ 1,459 milhao e atingir reducao minima de 20%."),("4","Preservar controles criticos","GED, rastreabilidade, conformidade, auditorias e ciclo documental.")]
y=H-52*mm
for n,tit,desc in items:
    c.setFillColor(ORANGE); c.setFont("Helvetica-Bold",18); c.drawString(20*mm,y,n)
    c.setFillColor(INK); c.setFont("Helvetica-Bold",13); c.drawString(34*mm,y,tit)
    c.setFillColor(MUTED); c.setFont("Helvetica",11); c.drawString(105*mm,y,desc)
    c.setStrokeColor(LIGHT); c.line(34*mm,y-8*mm,W-18*mm,y-8*mm); y-=29*mm
c.setFillColor(TEAL); c.roundRect(18*mm,25*mm,W-36*mm,20*mm,5,fill=1,stroke=0)
c.setFillColor(white); c.setFont("Helvetica-Bold",12); c.drawCentredString(W/2,33*mm,"APROVAR O MODELO E DETERMINAR REVISAO ECONOMICA ANTES DE RECONHECER A ECONOMIA")
c.showPage()

# 7
header("Fontes, premissas e ressalvas", "06 | GOVERNANCA DA INFORMACAO", 7)
sources=[
    "Baseline: HISTOGRAMA_Arquivo Tecnico + Doc Control _20-08-26_R10.xlsx - HIST MOI_Acordado com Borghesan.",
    "Doc Control: arquivo integrado R10 - aba HIST MOI_Doc Control.",
    "Arquivo Tecnico: arquivo integrado R10 - aba HIST MOI Arquivo Tecnico (684 HM reconciliados).",
    "Referencia visual: HISTOGRAMA_Arquivo Tecnico _20-08-26_R10.xlsx, localizado na pasta Revisao.",
    "Premissas: 220 HH/HM; escopo informado de aproximadamente 90% Doc Control e 10% Arquivo Tecnico; meta minima de reducao de 20%.",
    "Ressalva: o arquivo de referencia visual exibe 707 HM, mas suas linhas funcionais nao reconciliam; por isso seus numeros nao foram adotados.",
]
y=H-52*mm
for i,s in enumerate(sources,1):
    c.setFillColor(ORANGE); c.setFont("Helvetica-Bold",11); c.drawString(20*mm,y,f"{i:02d}")
    y=wrap(s,34*mm,y,W-56*mm,11,15,INK)-8*mm
c.showPage(); c.save()
reader=PdfReader(str(OUT)); assert len(reader.pages)==7
print(OUT, OUT.stat().st_size, len(reader.pages))
