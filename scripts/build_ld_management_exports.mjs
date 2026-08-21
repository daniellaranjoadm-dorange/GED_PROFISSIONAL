import fs from "node:fs/promises";
import { Workbook, SpreadsheetFile, Presentation, PresentationFile } from "@oai/artifact-tool";

const [inputPath, xlsxPath, pptxPath, previewDir] = process.argv.slice(2);
const payload = JSON.parse(await fs.readFile(inputPath, "utf8"));
const rows = payload.records;
const meta = payload.meta;

const columns = meta.ldHeaders;
const dateColumns = new Set([10,23,25,28,47,48,49,51,55,56,58,60]); // indices A=0
const cellValue = (value,index) => {
  if (!dateColumns.has(index) || !value) return value ?? "";
  const parsed = new Date(String(value).length === 10 ? `${value}T12:00:00` : value);
  return Number.isNaN(parsed.getTime()) ? value : parsed;
};

const wb = Workbook.create();
const sheet = wb.worksheets.add("LD Consolidada");
sheet.showGridLines = false;
const matrix = [columns, ...rows.map(r=>columns.map((_,i)=>cellValue(r.ldExport?.[i],i)))];
sheet.getRangeByIndexes(0,0,matrix.length,columns.length).values = matrix;
const header = sheet.getRangeByIndexes(0,0,1,columns.length);
header.format.fill = "#123B50";
header.format.font = { bold:true, color:"#FFFFFF", size:10 };
header.format.rowHeight = 30;
header.format.verticalAlignment = "center";
header.format.wrapText = true;
const body = sheet.getRangeByIndexes(1,0,rows.length,columns.length);
body.format.font = { color:"#17212B", size:9 };
body.format.verticalAlignment = "center";
body.format.borders = { preset:"inside", style:"thin", color:"#D9E3E8" };
body.format.rowHeight = 34;
sheet.freezePanes.freezeRows(1);
sheet.freezePanes.freezeColumns(2);
for (let i=0;i<columns.length;i++) {
  const label=columns[i];
  const col=sheet.getRangeByIndexes(0,i,rows.length+1,1);
  const normalized=label.normalize("NFD").replace(/[\u0300-\u036f]/g,"").toUpperCase();
  col.format.columnWidth = (/TITLE|TITULO/.test(normalized)?44:/DISCIPLIN/.test(normalized)?34:/DOCUMENTO|TRANSMITTAL|GRD|PCF/.test(normalized)?27:/STATUS|SPECIALTY|PURPOSE/.test(normalized)?22:16);
  if(/TITLE|TITULO|DISCIPLIN/.test(normalized)) sheet.getRangeByIndexes(1,i,rows.length,1).format.wrapText = true;
  if(dateColumns.has(i)) sheet.getRangeByIndexes(1,i,rows.length,1).setNumberFormat("dd/mm/yyyy");
  if(/QTD|COMMENTS|COMENTARIOS|UNDER REVIEW|PENDING/.test(normalized)) sheet.getRangeByIndexes(1,i,rows.length,1).setNumberFormat("#,##0");
}
const excelCol=n=>{let s="";while(n){n--;s=String.fromCharCode(65+n%26)+s;n=Math.floor(n/26)}return s};
sheet.tables.add(`A1:${excelCol(columns.length)}${rows.length+1}`, true, "LDConsolidada");
const xlsx = await SpreadsheetFile.exportXlsx(wb);
await xlsx.save(xlsxPath);
await fs.mkdir(previewDir,{recursive:true});
const xlsxPreview = await wb.render({sheetName:"LD Consolidada",range:"A1:L18",scale:1.4,format:"png"});
await fs.writeFile(`${previewDir}/excel-preview.png`,new Uint8Array(await xlsxPreview.arrayBuffer()));
console.log((await wb.inspect({kind:"table",range:"'LD Consolidada'!A1:L8",include:"values,formulas",tableMaxRows:8,tableMaxCols:12})).ndjson);

const total=rows.length;
const emitted=rows.filter(r=>r.statusEmissao==="Emitido").length;
const pending=total-emitted;
const pcfs=rows.filter(r=>r.pcf).length;
const notReleased=rows.filter(r=>r.statusPcf==="NOT RELEASED").length;
const open=rows.reduce((s,r)=>s+(Number(r.open)||0),0);
const overdue=rows.filter(r=>r.statusEmissao!=="Emitido"&&r.cronogramaTermino&&r.cronogramaTermino<meta.generated.slice(0,10)).length;
const approvedNoComments=rows.filter(r=>String(r.status||"").toLocaleLowerCase("pt-BR")==="aprovado sem comentários").length;
const disciplines=Object.entries(rows.reduce((a,r)=>{const k=r.disciplina||"Sem disciplina";a[k]=(a[k]||0)+1;return a;},{})).sort((a,b)=>b[1]-a[1]).slice(0,8);
const statusEntries=Object.entries(rows.reduce((a,r)=>{const k=r.status||"Sem status";a[k]=(a[k]||0)+1;return a;},{})).sort((a,b)=>b[1]-a[1]).slice(0,7);
const pct=n=>total?`${(n/total*100).toFixed(1).replace('.',',')}%`:"0%";

const deck=Presentation.create({slideSize:{width:1280,height:720}});
const C={bg:"#06131E",panel:"#0D2233",cyan:"#37C8F4",mint:"#1DD6B5",amber:"#FFAD32",red:"#FF5E68",white:"#F4FBFE",muted:"#9BB6C3"};
function text(slide,name,value,left,top,width,height,size=24,color=C.white,bold=false){const s=slide.shapes.add({geometry:"textbox",name,position:{left,top,width,height},fill:"none",line:{style:"solid",fill:"none",width:0}});s.text=value;s.text.style={fontSize:size,color,bold};return s}
function title(slide,value,kicker){text(slide,"kicker",kicker,72,42,700,24,14,C.cyan,true);text(slide,"title",value,72,72,1100,58,38,C.white,true);text(slide,"date",`Base consolidada · ${new Date(meta.generated).toLocaleString('pt-BR')}`,72,660,800,22,13,C.muted,false)}
function card(slide,x,y,w,label,value,color){slide.shapes.add({geometry:"roundRect",position:{left:x,top:y,width:w,height:126},fill:C.panel,line:{style:"solid",fill:color,width:2},borderRadius:"rounded-xl"});text(slide,`card-${label}`,label.toUpperCase(),x+20,y+18,w-40,22,13,C.muted,true);text(slide,`value-${label}`,String(value),x+20,y+48,w-40,56,36,color,true)}

let s=deck.slides.add();s.background.fill=C.bg;text(s,"brand","D’OR@NGE · DOCUMENT CONTROL",72,62,600,30,16,C.amber,true);text(s,"cover","LD Projeto Básico",72,174,900,72,54,C.white,true);text(s,"cover-sub","Apresentação Gerencial da Carteira Documental",72,258,850,44,28,C.cyan,false);text(s,"scope",`${total} documentos consolidados · última revisão válida por documento`,72,340,760,34,21,C.muted,false);text(s,"generated",new Date(meta.generated).toLocaleString('pt-BR'),72,622,500,24,14,C.muted,false);

s=deck.slides.add();s.background.fill=C.bg;title(s,"Resumo executivo","01 · POSIÇÃO DA CARTEIRA");card(s,72,170,204,"Documentos",total,C.cyan);card(s,294,170,204,"Emitidos",emitted,C.mint);card(s,516,170,204,"Aprovados s/ comentários",approvedNoComments,"#48D7A8");card(s,738,170,204,"Pendentes",pending,C.amber);card(s,960,170,204,"Vencidos",overdue,C.red);text(s,"reading","Leitura gerencial",72,350,320,34,24,C.white,true);text(s,"reading-body",`A carteira possui ${emitted} documentos emitidos e ${approvedNoComments} aprovados sem comentários. Permanecem ${pending} documentos não emitidos, ${overdue} itens vencidos e ${open} comentários OPEN que requerem coordenação entre Engenharia e Document Control.`,72,398,1080,120,24,C.muted,false);

s=deck.slides.add();s.background.fill=C.bg;title(s,"Produção por disciplina","02 · CAPACIDADE E CARGA");s.charts.add("bar",{position:{left:72,top:160,width:1120,height:430},categories:disciplines.map(x=>x[0]),series:[{name:"Documentos",values:disciplines.map(x=>x[1]),fill:C.cyan}],hasLegend:false,dataLabels:{showValue:true,position:"outEnd"},xAxis:{majorGridlines:{style:"solid",fill:"#234359",width:1}}});

s=deck.slides.add();s.background.fill=C.bg;title(s,"Situação documental","03 · STATUS E APROVAÇÃO");s.charts.add("bar",{position:{left:72,top:160,width:700,height:430},categories:statusEntries.map(x=>x[0]),series:[{name:"Documentos",values:statusEntries.map(x=>x[1]),fill:C.mint}],hasLegend:false,dataLabels:{showValue:true,position:"outEnd"},xAxis:{majorGridlines:{style:"solid",fill:"#234359",width:1}}});card(s,830,182,320,"PCFs recebidas",pcfs,C.cyan);card(s,830,330,320,"PCFs não liberadas",notReleased,C.red);card(s,830,478,320,"Comentários OPEN",open,C.amber);

s=deck.slides.add();s.background.fill=C.bg;title(s,"Prioridades de atuação","04 · DECISÕES RECOMENDADAS");const actions=[["1","Eliminar vencimentos",`${overdue} documentos vencidos não emitidos`,C.red],["2","Atacar pendências de emissão",`${pending} documentos aguardam emissão`,C.amber],["3","Destravar aprovações",`${notReleased} PCFs estão NOT RELEASED`,C.cyan],["4","Fechar comentários",`${open} comentários permanecem OPEN`,C.mint]];actions.forEach((a,i)=>{const y=162+i*108;text(s,`n${i}`,a[0],72,y,48,48,30,a[3],true);text(s,`a${i}`,a[1],142,y,440,34,24,C.white,true);text(s,`d${i}`,a[2],142,y+38,760,30,18,C.muted,false)});

await fs.writeFile(`${previewDir}/source-notes.txt`,`Fonte: ${meta.source}\nBase consolidada: última revisão válida por documento.\nGerado em: ${meta.generated}\n`);
for(const [i,slide] of deck.slides.items.entries()){const png=await deck.export({slide,format:"png",scale:1});await fs.writeFile(`${previewDir}/slide-${i+1}.png`,new Uint8Array(await png.arrayBuffer()));const layout=await slide.export({format:"layout"});await fs.writeFile(`${previewDir}/slide-${i+1}.layout.json`,await layout.text())}
const montage=await deck.export({format:"webp",montage:true,scale:1});await fs.writeFile(`${previewDir}/deck-montage.webp`,new Uint8Array(await montage.arrayBuffer()));
const pptx=await PresentationFile.exportPptx(deck);await pptx.save(pptxPath);
console.log((await deck.inspect({kind:"slide,textbox,chart",maxChars:5000})).ndjson);
