from pathlib import Path
from reportlab.pdfgen import canvas
from reportlab.lib.pagesizes import A4, landscape
from reportlab.lib.colors import HexColor, white
from reportlab.lib.units import mm
from reportlab.pdfbase.pdfmetrics import stringWidth
from pypdf import PdfReader, PdfWriter

OUT=Path(r"D:\GED_PROFISSIONAL\outputs\pacote_diretoria_r15_analista\RELATORIO_EXECUTIVO_GESTAO_INTEGRADA_R15_ANALISTA_COMPARTILHADO.pdf"); TMP=OUT.with_name('relatorio_sem_organograma.tmp.pdf')
W,H=landscape(A4); NAVY=HexColor('#17365D'); TEAL=HexColor('#0F6B78'); CYAN=HexColor('#35C7E8'); ORANGE=HexColor('#F7931E'); INK=HexColor('#17324D'); MUTED=HexColor('#657C8C'); LIGHT=HexColor('#DCE6F1'); GREEN=HexColor('#E2F0D9'); AMBER=HexColor('#FFF2CC'); RED=HexColor('#FCE4D6')
c=canvas.Canvas(str(TMP),pagesize=(W,H))
def footer(p): c.setFillColor(MUTED);c.setFont('Helvetica',8);c.drawString(18*mm,9*mm,"D'OR@NGE | Gestao Integrada | R14 Saving | 20/08/2026");c.drawRightString(W-18*mm,9*mm,f'Pagina {p}')
def header(t,k,p): c.setFillColor(NAVY);c.rect(0,H-28*mm,W,28*mm,fill=1,stroke=0);c.setFillColor(ORANGE);c.setFont('Helvetica-Bold',9);c.drawString(18*mm,H-10*mm,k);c.setFillColor(white);c.setFont('Helvetica-Bold',20);c.drawString(18*mm,H-21*mm,t);footer(p)
def wrap(t,x,y,w,size=11,leading=15,color=INK,bold=False):
 f='Helvetica-Bold' if bold else 'Helvetica';c.setFont(f,size);c.setFillColor(color);line='';yy=y
 for word in t.split():
  q=(line+' '+word).strip()
  if line and stringWidth(q,f,size)>w:c.drawString(x,yy,line);yy-=leading;line=word
  else:line=q
 if line:c.drawString(x,yy,line);yy-=leading
 return yy
def card(x,y,w,label,value,sub,color): c.setFillColor(HexColor('#F7FAFC'));c.roundRect(x,y,w,34*mm,5,fill=1,stroke=0);c.setStrokeColor(color);c.roundRect(x,y,w,34*mm,5,fill=0,stroke=1);c.setFillColor(MUTED);c.setFont('Helvetica-Bold',8);c.drawString(x+8,y+25*mm,label.upper());c.setFillColor(color);c.setFont('Helvetica-Bold',16);c.drawString(x+8,y+14*mm,value);c.setFillColor(MUTED);c.setFont('Helvetica',8);c.drawString(x+8,y+5*mm,sub)

header('Gestao Integrada de Document Control','EXECUTIVE DECISION - META SUPERADA',1);c.setFillColor(INK);c.setFont('Helvetica-Bold',29);c.drawString(18*mm,H-56*mm,'O Analista de Qualidade compartilhado');c.drawString(18*mm,H-70*mm,'eleva o saving consolidado para 24,90%.');c.setFillColor(TEAL);c.roundRect(18*mm,H-127*mm,W-36*mm,34*mm,6,fill=1,stroke=0);wrap('Custo consolidado: R$ 5,475 milhoes | Saving: R$ 1,815 milhao | Meta superada em R$ 357,2 mil',26*mm,H-108*mm,W-52*mm,14,18,white,True);c.showPage()

header('Resultado consolidado','01 | VISAO EXECUTIVA',2);items=[('Custo acordado','R$ 7,290 mi','baseline',CYAN),('Custo reduzido','R$ 5,475 mi','DC + Arquivo',TEAL),('Saving real','R$ 1,815 mi','24,90%',TEAL),('Meta 20%','R$ 5,832 mi','custo-alvo',ORANGE),('Superacao','R$ 357,2 mil','4,90 p.p.',TEAL)]
for i,v in enumerate(items):card((18+i*52)*mm,H-80*mm,46*mm,*v)
c.setFillColor(GREEN);c.roundRect(18*mm,H-137*mm,W-36*mm,38*mm,5,fill=1,stroke=0);wrap('O plano supera a meta em R$ 357,2 mil. A decisao e aprovar a baseline e formalizar o Analista compartilhado com guardrails de qualidade.',25*mm,H-113*mm,W-50*mm,14,19,INK,True);c.showPage()

header('Reducao do Arquivo Tecnico','02 | DRIVER DO SAVING',3);items=[('HM anterior','684 HM','estrutura transferida',ORANGE),('HM reduzido','338 HM','nova baseline',TEAL),('Reducao','346 HM','50,6%',TEAL),('Custo anterior','R$ 3,621 mi','Arquivo Tecnico',ORANGE),('Custo reduzido','R$ 1,805 mi','saving R$ 1,816 mi',TEAL)]
for i,v in enumerate(items):card((18+i*52)*mm,H-80*mm,46*mm,*v)
wrap('Escopo preservado: impressao, carimbos, distribuicao, recolhimento e guarda fisica. A aprovacao deve exigir acompanhamento de backlog, prazo e disponibilidade.',18*mm,55*mm,W-36*mm,13,18,INK,True);c.showPage()

header('Capacidade e guardrails','03 | SUSTENTABILIDADE',4);items=[('HM acordado','1.028,5','baseline',CYAN),('HM consolidado','767,5','-25,4%',TEAL),('HH economizadas','57.420','220 HH/HM',TEAL),('Pico anterior','24 MOI','separado',ORANGE),('Pico reduzido','16 MOI','nova curva',TEAL)]
for i,v in enumerate(items):card((18+i*52)*mm,H-80*mm,46*mm,*v)
wrap('Guardrails: backlog documental, prazo de distribuicao, recolhimento de obsoletos, disponibilidade do arquivo e gatilho de reforecast por desvio sustentado.',18*mm,55*mm,W-36*mm,13,18,INK,True);c.showPage()

header('Benchmark da Gestao PJ','04 | EFICIENCIA DO MODELO',5);items=[('Gestao PJ','R$ 11.000','governanca transversal',TEAL),('Supervisor Niteroi','R$ 11.850','PJ 7,2% menor',CYAN),('Supervisor GLP/RG','R$ 14.670','PJ 25,0% menor',ORANGE),('Duas supervisoes','R$ 26.520','PJ 58,5% menor',HexColor('#C00000'))]
for i,v in enumerate(items):card((18+i*65)*mm,H-80*mm,58*mm,*v)
wrap('Benchmark exclusivamente financeiro. O enquadramento deve considerar a responsabilidade consolidada por tres contratos, sem formula por contrato.',18*mm,55*mm,W-36*mm,12,17,INK,True);c.showPage()

header('Decisao recomendada','05 | ENCAMINHAMENTO',6);y=H-52*mm
for n,t,d in [('01','Reconhecer o saving','R$ 1,815 milhao e 24,90% de reducao consolidada.'),('02','Aprovar a nova baseline','767,5 HM e pico de 16 MOI.'),('03','Formalizar recurso compartilhado','Analista para Handy Size, GLP e MR1.'),('04','Manter governanca','Indicadores, guardrails e reforecast por desvio.')]:
 c.setFillColor(ORANGE);c.setFont('Helvetica-Bold',18);c.drawString(20*mm,y,n);c.setFillColor(INK);c.setFont('Helvetica-Bold',13);c.drawString(34*mm,y,t);c.setFillColor(MUTED);c.setFont('Helvetica',11);c.drawString(105*mm,y,d);y-=29*mm
c.setFillColor(TEAL);c.roundRect(18*mm,25*mm,W-36*mm,20*mm,5,fill=1,stroke=0);c.setFillColor(white);c.setFont('Helvetica-Bold',12);c.drawCentredString(W/2,33*mm,'APROVAR O CENARIO, O ORGANOGRAMA REV11 E A GOVERNANCA COMPARTILHADA');c.showPage();c.save();w=PdfWriter();w.append(str(TMP));w.append(r'D:\Doc Control\Organogramas\Organograma Doc Control_Rev11.pdf');w.write(str(OUT));TMP.unlink();r=PdfReader(str(OUT));assert len(r.pages)==7;print(OUT,OUT.stat().st_size)
