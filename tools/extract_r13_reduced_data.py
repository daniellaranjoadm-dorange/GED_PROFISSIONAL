from pathlib import Path
import openpyxl, json

src=Path(r"D:\Doc Control\Histogramas\PACOTE_DASHBOARD_DIRETORIA_R12_ENTERPRISE\HISTOGRAMA_INTEGRADO_DOC_CONTROL_ARQUIVO_TECNICO_R13_ENTERPRISE.xlsx")
base=Path(r"D:\GED_PROFISSIONAL\tmp\integrated_r11\source_data.json")
out=Path(r"D:\GED_PROFISSIONAL\tmp\enterprise_r14_saving\source_data.json")
data=json.loads(base.read_text(encoding='utf-8'))
wb=openpyxl.load_workbook(src,data_only=True,read_only=False)
ws=wb['HIST_ARQUIVO_TECNICO']
projects=['Handy Size','Gaseiros / GLP','Mid Range / MR1']
mapping={
 'Assistente Documentação':[5,6,7],
 'Auxiliar Documentação':[8,9,10],
 'Analista Qualidade':[11,12,13],
}
roles={}
for role,rows in mapping.items():
    roles[role]={}
    for project,row in zip(projects,rows):
        roles[role][project]=[ws.cell(row,c).value or 0 for c in range(7,75)]
data['archive']['roles']=roles
data['archive']['projects']={p:[sum(roles[r][p][i] for r in roles) for i in range(68)] for p in projects}
data['archive']['total']=[sum(data['archive']['projects'][p][i] for p in projects) for i in range(68)]
out.parent.mkdir(parents=True,exist_ok=True)
out.write_text(json.dumps(data,ensure_ascii=False,indent=2),encoding='utf-8')
print({'archive_hm':sum(data['archive']['total']),'archive_peak':max(data['archive']['total']),'combined_hm':sum(data['archive']['total'])+sum(data['doc_control']['total']),'combined_peak':max(a+b for a,b in zip(data['archive']['total'],data['doc_control']['total'])),'project_hm':{p:sum(v) for p,v in data['archive']['projects'].items()}})
