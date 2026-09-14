"""Substitui a aba Qualidade pelo cockpit de Propostas Técnicas críticas."""

from __future__ import annotations

import re
import sys
from pathlib import Path


MARKER = "pt-critical-v1"

SECTION = r'''<section id="qualidade" class="view pt-critical-view">
<article class="hero glass pt-critical-hero"><div><div class="eyebrow">Prioridade contratual · Propostas Técnicas</div><h2>Propostas Técnicas Críticas</h2><p>Visão executiva das PTs previstas, emitidas, próximas do prazo e com tratativas de comentários. Os indicadores e a lista são calculados diretamente da LD vigente.</p></div><div class="stamp"><div class="label">Escopo crítico</div><div class="value" id="ptHeroTotal">—</div><small>Propostas Técnicas monitoradas</small></div></article>
<div id="qualityGrid" hidden></div><div class="pt-kpi-grid" id="ptKpis"></div>
<div class="grid2 pt-analysis-grid"><article class="card glass"><h3>Situação das Propostas Técnicas</h3><p class="intro">Distribuição operacional da carteira contratual.</p><div class="bar-list" id="ptSituationBars"></div></article><article class="card glass"><h3>Pressão por disciplina</h3><p class="intro">Disciplinas com maior pontuação de criticidade.</p><div class="bar-list" id="ptDisciplineBars"></div></article></div>
<article class="card glass pt-table-card"><div class="pt-table-head"><div><h3>Ranking de criticidade das PTs</h3><p class="intro">Ordenação: vencimento, NOT RELEASED, proximidade do prazo, OPEN e UNDER REVIEW.</p></div><strong id="ptCount"></strong></div><div class="pt-toolbar"><input class="control" id="ptSearch" placeholder="Buscar em todas as colunas das PTs..."><select class="control" id="ptQuickFilter"><option value="ALL">Todas as PTs</option><option value="PLANNED">Previstas</option><option value="EMITTED">Emitidas</option><option value="NEAR">Próximas do prazo</option><option value="OVERDUE">Vencidas</option><option value="NOT_RELEASED">NOT RELEASED</option><option value="OPEN">Com OPEN</option><option value="UNDER">Com UNDER REVIEW</option><option value="AWAITING_PCF">Aguardando PCF</option></select></div><div class="table-wrap pt-table-wrap"><table class="pt-table"><thead><tr><th>Prioridade</th><th>Nº DOX</th><th>Nº Transpetro</th><th>Rev.</th><th>Título</th><th>Disciplina</th><th>Situação</th><th>Prazo</th><th>PCF</th><th>Status PCF</th><th>OPEN</th><th>UNDER REVIEW</th></tr></thead><tbody id="ptRows"></tbody></table></div></article>
</section>'''

STYLE = r'''
<style id="pt-critical-v1">
.nav button[data-view="qualidade"]{border-color:rgba(255,173,50,.38)}.nav button[data-view="qualidade"] .nav-index{background:#4a3013;color:#ffd28b}.pt-critical-hero{border-left-color:#ffad32!important}.pt-kpi-grid{display:grid;grid-template-columns:repeat(4,minmax(0,1fr));gap:12px;margin:18px 0}.pt-kpi{position:relative;padding:17px;border:1px solid #27495f;border-radius:15px;background:#0a2030;overflow:hidden}.pt-kpi:before{content:"";position:absolute;left:0;top:0;right:0;height:3px;background:var(--pt-color,#37c8f4)}.pt-kpi span{display:block;color:#8fb1c2;font-size:9px;font-weight:900;letter-spacing:.09em;text-transform:uppercase}.pt-kpi strong{display:block;margin:13px 0 4px;color:#fff;font-size:29px}.pt-kpi small{color:#91afbe;font-size:10px}.pt-analysis-grid{margin-bottom:16px}.pt-analysis-grid .card{min-height:330px}.pt-table-card{padding-bottom:10px!important}.pt-table-head{display:flex;justify-content:space-between;align-items:start;gap:15px}.pt-toolbar{display:grid;grid-template-columns:1fr 280px;gap:10px;margin:14px 0}.pt-table-wrap{max-height:590px}.pt-table{min-width:1450px}.pt-table th{position:sticky;top:0;z-index:2}.pt-table td:nth-child(5){min-width:330px}.pt-priority{display:inline-flex;min-width:62px;justify-content:center;padding:5px 7px;border-radius:999px;font-size:9px;font-weight:950}.pt-p1{background:#5a1720;color:#ffadb4}.pt-p2{background:#5a3510;color:#ffd18b}.pt-p3{background:#123d35;color:#89efd9}.pt-signals{display:flex;gap:4px;flex-wrap:wrap;min-width:210px}.pt-signal{padding:4px 6px;border-radius:999px;background:#17354a;color:#bdeaff;font-size:8px;font-weight:900;white-space:nowrap}.pt-signal.danger{background:#5a1720;color:#ffb2ba}.pt-signal.warn{background:#583810;color:#ffd18b}.pt-signal.good{background:#124238;color:#8cf0dc}.pt-doc-link{color:#72dcff;text-decoration:none}.pt-doc-link:hover{text-decoration:underline;color:#fff}.pt-bar-note{display:flex;justify-content:space-between;color:#9ab5c2;font-size:10px;margin-bottom:4px}.pt-bar-track{height:10px;background:#102b3d;border-radius:999px;overflow:hidden;margin-bottom:13px}.pt-bar-fill{height:100%;border-radius:inherit;background:var(--bar-color,#37c8f4)}
@media(max-width:1100px){.pt-kpi-grid{grid-template-columns:repeat(2,1fr)}}@media(max-width:700px){.pt-kpi-grid{grid-template-columns:1fr}.pt-toolbar{grid-template-columns:1fr}}
</style>'''

SCRIPT = r'''
<script>
(()=>{
  const ptData=DATA.filter(r=>String(r.tipo||'').trim().toUpperCase()==='PT');
  const ptToday=new Date((META.generated||new Date().toISOString()).slice(0,10)+'T00:00:00');
  const n=v=>Number(v)||0,date=v=>v?new Date(String(v).slice(0,10)+'T00:00:00'):null;
  const emitted=r=>r.statusEmissao==='Emitido',planned=r=>!emitted(r),notReleased=r=>r.statusPcf==='NOT RELEASED';
  const daysToEnd=r=>{const d=date(r.cronogramaTermino);return d?Math.ceil((d-ptToday)/86400000):null};
  const overdue=r=>planned(r)&&daysToEnd(r)!==null&&daysToEnd(r)<0;
  const near=r=>planned(r)&&daysToEnd(r)!==null&&daysToEnd(r)>=0&&daysToEnd(r)<=30;
  const awaitingPcf=r=>emitted(r)&&!String(r.pcf||'').trim();
  const score=r=>(overdue(r)?10000:0)+(notReleased(r)?7000:0)+(near(r)?4000-Math.max(daysToEnd(r)||0,0):0)+(awaitingPcf(r)?3000:0)+n(r.open)*20+n(r.underReview)*10+(planned(r)&&daysToEnd(r)===null?1500:0);
  const priority=r=>score(r)>=7000?['P1','pt-p1']:score(r)>=3000?['P2','pt-p2']:['P3','pt-p3'];
  const escPt=v=>String(v??'').replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
  const fmtPt=new Intl.NumberFormat('pt-BR'),fmtDate=v=>{const d=date(v);return d?d.toLocaleDateString('pt-BR'):'—'};
  const safePt=u=>/^https?:\/\//i.test(String(u||''))?String(u):'';
  const linkPt=(label,url)=>safePt(url)?`<a class="pt-doc-link" href="${escPt(url)}" target="_blank" rel="noopener">${escPt(label||'—')} ↗</a>`:escPt(label||'—');
  const signals=r=>{const a=[];a.push(emitted(r)?['EMITIDA','good']:['PREVISTA','']);if(overdue(r))a.push(['VENCIDA','danger']);else if(near(r))a.push(['PRÓXIMA DO PRAZO','warn']);if(awaitingPcf(r))a.push(['AGUARDANDO PCF','warn']);if(notReleased(r))a.push(['NOT RELEASED','danger']);if(n(r.open)>0)a.push([`${n(r.open)} OPEN`,'danger']);if(n(r.underReview)>0)a.push([`${n(r.underReview)} UNDER REVIEW`,'warn']);if(r.statusPcf==='RELEASED')a.push(['RELEASED','good']);return a};
  const metrics=[
    ['PTs no contrato',ptData.length,'#37c8f4','carteira monitorada'],
    ['Previstas',ptData.filter(planned).length,'#ffad32','ainda não emitidas'],
    ['Emitidas',ptData.filter(emitted).length,'#1dd6b5','emissão concluída'],
    ['Próximas do prazo',ptData.filter(near).length,'#ffbf5d','até 30 dias'],
    ['NOT RELEASED',ptData.filter(notReleased).length,'#ff6670','requerem nova tratativa'],
    ['Documentos com OPEN',ptData.filter(r=>n(r.open)>0).length,'#ff6670',`${fmtPt.format(ptData.reduce((s,r)=>s+n(r.open),0))} comentários OPEN`],
    ['Com UNDER REVIEW',ptData.filter(r=>n(r.underReview)>0).length,'#9a83ff',`${fmtPt.format(ptData.reduce((s,r)=>s+n(r.underReview),0))} em análise`],
    ['Aprovadas sem comentários',ptData.filter(r=>String(r.status||'').trim().toLocaleLowerCase('pt-BR')==='aprovado sem comentários').length,'#1dd6b5','aprovação sem ressalvas']
  ];
  document.getElementById('ptHeroTotal').textContent=`${fmtPt.format(ptData.length)} PTs`;
  document.getElementById('ptKpis').innerHTML=metrics.map(m=>`<article class="pt-kpi" style="--pt-color:${m[2]}"><span>${m[0]}</span><strong>${fmtPt.format(m[1])}</strong><small>${m[3]}</small></article>`).join('');
  function bars(id,items){const max=Math.max(...items.map(x=>x[1]),1);document.getElementById(id).innerHTML=items.map(x=>`<div class="pt-bar-note"><strong>${escPt(x[0])}</strong><span>${fmtPt.format(x[1])}</span></div><div class="pt-bar-track"><div class="pt-bar-fill" style="width:${x[1]/max*100}%;--bar-color:${x[2]||'#37c8f4'}"></div></div>`).join('')}
  bars('ptSituationBars',[['Previstas',ptData.filter(planned).length,'#ffad32'],['Emitidas',ptData.filter(emitted).length,'#1dd6b5'],['NOT RELEASED',ptData.filter(notReleased).length,'#ff6670'],['Com OPEN',ptData.filter(r=>n(r.open)>0).length,'#ff6670'],['UNDER REVIEW',ptData.filter(r=>n(r.underReview)>0).length,'#9a83ff'],['Aprovadas sem comentários',ptData.filter(r=>String(r.status||'').trim().toLocaleLowerCase('pt-BR')==='aprovado sem comentários').length,'#1dd6b5'],['Aprovadas com comentários',ptData.filter(r=>String(r.status||'').trim().toLocaleLowerCase('pt-BR')==='aprovado com comentários').length,'#55c8f4'],['Reprovadas',ptData.filter(r=>String(r.status||'').trim().toLocaleLowerCase('pt-BR')==='reprovado').length,'#ff6670'],['Aguardando PCF',ptData.filter(awaitingPcf).length,'#60a5fa']]);
  const byDiscipline={};ptData.forEach(r=>{const k=r.disciplina||'Sem disciplina';byDiscipline[k]=(byDiscipline[k]||0)+score(r)});bars('ptDisciplineBars',Object.entries(byDiscipline).sort((a,b)=>b[1]-a[1]).slice(0,8).map(x=>[x[0],x[1],'#37c8f4']));
  function selected(r,f){return f==='ALL'||f==='PLANNED'&&planned(r)||f==='EMITTED'&&emitted(r)||f==='NEAR'&&near(r)||f==='OVERDUE'&&overdue(r)||f==='NOT_RELEASED'&&notReleased(r)||f==='OPEN'&&n(r.open)>0||f==='UNDER'&&n(r.underReview)>0||f==='AWAITING_PCF'&&awaitingPcf(r)}
  function renderPt(){const q=document.getElementById('ptSearch').value.trim().toLocaleLowerCase('pt-BR'),f=document.getElementById('ptQuickFilter').value;const rows=ptData.filter(r=>selected(r,f)&&(!q||Object.values(r).some(v=>(Array.isArray(v)?v:[v]).some(x=>String(x??'').toLocaleLowerCase('pt-BR').includes(q))))).sort((a,b)=>score(b)-score(a));document.getElementById('ptCount').textContent=`${fmtPt.format(rows.length)} PTs`;document.getElementById('ptRows').innerHTML=rows.map(r=>{const p=priority(r),sig=signals(r).map(x=>`<span class="pt-signal ${x[1]}">${escPt(x[0])}</span>`).join('');return `<tr><td><span class="pt-priority ${p[1]}">${p[0]}</span></td><td>${linkPt(r.ldExport?.[1]||'—',r.linkDox)}</td><td><strong>${escPt(r.documento)}</strong></td><td>${escPt(r.revisao)}</td><td>${escPt(r.titulo)}</td><td>${escPt(r.disciplina)}</td><td><div class="pt-signals">${sig}</div></td><td>${fmtDate(r.cronogramaTermino)}</td><td>${linkPt(r.pcf||'—',r.linkPcf)}</td><td>${escPt(r.statusPcf)}</td><td><strong>${fmtPt.format(n(r.open))}</strong></td><td><strong>${fmtPt.format(n(r.underReview))}</strong></td></tr>`}).join('')}
  document.getElementById('ptSearch').addEventListener('input',renderPt);document.getElementById('ptQuickFilter').addEventListener('change',renderPt);renderPt();
})();
</script>'''


def update(path: Path) -> None:
    text = path.read_text(encoding="utf-8")
    if MARKER in text:
        # O HTML do relatório PDF contém um </body> literal dentro de uma
        # template string. Garanta que o script seja anexado ao body externo,
        # que é sempre a última ocorrência do fechamento no arquivo.
        if SCRIPT in text:
            text = text.replace(SCRIPT, "", 1)
        body_end = text.rfind("</body>")
        if body_end < 0:
            raise RuntimeError(f"Fechamento </body> não encontrado: {path}")
        text = text[:body_end] + SCRIPT + text[body_end:]
        if 'id="qualityGrid"' not in text:
            text = text.replace(
                '<div class="pt-kpi-grid" id="ptKpis"></div>',
                '<div id="qualityGrid" hidden></div><div class="pt-kpi-grid" id="ptKpis"></div>',
                1,
            )
        temporary = path.with_suffix(path.suffix + ".tmp")
        temporary.write_text(text, encoding="utf-8")
        temporary.replace(path)
        print(f"POSICAO_SCRIPT_OK|{path}|{path.stat().st_size}")
        return
    text, nav_count = re.subn(
        r'(<button data-view="qualidade"><span class="nav-index">)03(</span><span class="nav-copy"><strong>)Qualidade(</strong><small>)Confiabilidade da base(</small></span></button>)',
        r'\g<1>03\g<2>PTs Críticas\g<3>Prioridade contratual\g<4>',
        text,
        count=1,
    )
    text, section_count = re.subn(
        r'<section id="qualidade" class="view">.*?</section>',
        SECTION,
        text,
        count=1,
        flags=re.DOTALL,
    )
    if nav_count != 1 or section_count != 1:
        raise RuntimeError(f"Estrutura esperada não encontrada em {path}: nav={nav_count}, section={section_count}")
    text = text.replace("</head>", STYLE + "</head>", 1)
    body_end = text.rfind("</body>")
    if body_end < 0:
        raise RuntimeError(f"Fechamento </body> não encontrado: {path}")
    text = text[:body_end] + SCRIPT + text[body_end:]
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(text, encoding="utf-8")
    temporary.replace(path)
    print(f"OK|{path}|{path.stat().st_size}")


if __name__ == "__main__":
    for argument in sys.argv[1:]:
        update(Path(argument))
