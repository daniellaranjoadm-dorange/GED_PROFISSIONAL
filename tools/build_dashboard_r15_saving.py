from pathlib import Path
import json,re
src=Path(r"D:\GED_PROFISSIONAL\outputs\pacote_diretoria_r12_enterprise\DASHBOARD_GESTAO_INTEGRADA_DOC_CONTROL_R14_ENTERPRISE.html")
out=Path(r"D:\GED_PROFISSIONAL\outputs\pacote_diretoria_r15_analista\DASHBOARD_GESTAO_INTEGRADA_DOC_CONTROL_R16_ANALISTA_COMPARTILHADO.html")
s=src.read_text(encoding='utf-8')
s=s.replace('R14 Enterprise - Escopo Separado','R16 Analista Compartilhado')
s=s.replace('Formalizar a governança integrada e recalibrar o custo consolidado','Aprovar a baseline que supera a meta de 20%')
s=s.replace('A separação entre Doc Control e Arquivo Técnico organiza responsabilidades, mas o custo total permanece praticamente no nível acordado. A redução deve ser medida no consolidado dos dois setores e atingir <strong>20% ou mais</strong>.','O Analista de Qualidade compartilhado entre Handy Size, GLP e MR1 elimina duplicidade e leva o saving consolidado para <strong>R$ 1,815 milhão (24,90%)</strong>, superando a meta de 20% em R$ 357,2 mil.')
repls={
'R$ 7,291 mi':'R$ 5,475 mi','Doc Control + Arquivo':'Analista compartilhado','≈ 0,0%':'24,90%','meta da Diretoria ≥ 20%':'4,90 p.p. acima da meta','1.113,5':'767,5','+85 HM vs. acordado':'−261 HM vs. acordado','R$ 1,459 mi':'R$ 357,2 mil','redução adicional necessária':'superação da meta de 20%',
'HISTOGRAMA_INTEGRADO_DOC_CONTROL_ARQUIVO_TECNICO_R12_ENTERPRISE.xlsx':'HISTOGRAMA_INTEGRADO_DOC_CONTROL_ARQUIVO_TECNICO_R15_ANALISTA_COMPARTILHADO.xlsx',
'APRESENTACAO_EXECUTIVA_GESTAO_INTEGRADA_R12_ENTERPRISE.pptx':'APRESENTACAO_EXECUTIVA_GESTAO_INTEGRADA_R15_ANALISTA_COMPARTILHADO.pptx',
'RELATORIO_EXECUTIVO_GESTAO_INTEGRADA_R12_ENTERPRISE.pdf':'RELATORIO_EXECUTIVO_GESTAO_INTEGRADA_R15_ANALISTA_COMPARTILHADO.pdf',
'Base auditável · R12':'Base auditável · R15','Diretoria · R12':'Diretoria · R15'}
for a,b in repls.items(): s=s.replace(a,b)
data=json.loads(Path(r"D:\GED_PROFISSIONAL\tmp\enterprise_r15_analista\source_data.json").read_text(encoding='utf-8'))
m=re.search(r'const DATA=(\{.*?\});\s*const EMBEDDED_FILES=',s,re.S)
if m:
    d=json.loads(m.group(1)); base=7290570.241
    salaries={'Gestão Doc Control':11000,'Supervisor Arquivo Técnico':11850,'Técnico Documentação':8122.053,'Assistente Documentação':5884.768,'Auxiliar Documentação':4710,'Analista Qualidade':5548.168}
    def role_cost(obj,role): return sum(sum(v) for v in obj['roles'][role].values())*salaries[role]
    dc_cost=sum(role_cost(data['doc_control'],r) for r in data['doc_control']['roles'])
    at_cost=sum(role_cost(data['archive'],r) for r in data['archive']['roles'])
    total=dc_cost+at_cost; hm=sum(data['doc_control']['total'])+sum(data['archive']['total']); saving=base-total
    d['summary']=[['HM ACORDADO','HM REDUZIDO','REDUÇÃO HM','REDUÇÃO HM %','HH ECONOMIZADAS','CUSTO COMPLETO','CUSTO REDUZIDO','ECONOMIA R$','ECONOMIA %','PICO REDUZIDO'],[1028.5,hm,1028.5-hm,(1028.5-hm)/1028.5,(1028.5-hm)*220,base,total,saving,saving/base,max(a+b for a,b in zip(data['doc_control']['total'],data['archive']['total']))]]
    monthly=[['Mês Global','MOI Completo','MOI Reduzido','Redução MOI','Custo Completo','Custo Reduzido','Economia Mensal','Economia Acumulada']]; acc=0
    for i in range(68):
        red=data['doc_control']['total'][i]+data['archive']['total'][i]
        rc=sum(sum(data[x]['roles'][r][p][i] for p in data[x]['roles'][r]) * salaries[r] for x in ('doc_control','archive') for r in data[x]['roles'])
        bc=d['monthly'][i+1][4] if i+1<len(d['monthly']) else 0; eco=bc-rc; acc+=eco; monthly.append([i+1,data['agreed']['total'][i],red,data['agreed']['total'][i]-red,bc,rc,eco,acc])
    d['monthly']=monthly
    s=s[:m.start(1)]+json.dumps(d,ensure_ascii=False,separators=(',',':'))+s[m.end(1):]
insert='<article class="decision glass"><div><div class="eyebrow">Analista de Qualidade compartilhado</div><h2>Um recurso para Handy Size, GLP e MR1</h2><p>O Arquivo Técnico cai para <strong>338 HM</strong>; o custo consolidado chega a <strong>R$ 5,475 milhões</strong> e o saving alcança <strong>24,90%</strong>.</p></div><div class="decision-card"><div class="label">Resultado consolidado</div><div class="value">R$ 1,815 mi</div><small>R$ 357,2 mil acima da meta</small></div></article>'
s=s.replace('<section id="estrutura" class="view">','<section id="estrutura" class="view">'+insert)
s=s.replace('<section id="organograma" class="view">','<section id="organograma" class="view"><article class="decision glass"><div><div class="eyebrow">Organograma oficial Rev11</div><h2>Estrutura aprovada como referência</h2><p>O organograma oficial está disponível no arquivo original, preservado sem alteração.</p></div><div class="decision-card"><a class="resource-btn" href="Organograma Doc Control_Rev11.pdf"><span class="file-icon">PDF</span><span class="button-copy"><small>Organograma oficial</small><strong>Abrir Rev11</strong></span></a></div></article>')
out.parent.mkdir(parents=True,exist_ok=True);out.write_text(s,encoding='utf-8');print(out,out.stat().st_size)
