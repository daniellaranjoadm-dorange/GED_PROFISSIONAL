Correção Lista LD

1. Origem:
- O filtro não depende mais de hasattr().
- As opções LD e LD Marenova aparecem mesmo se a base estiver sem registros distintos carregados.
- A comparação ignora maiúsculas/minúsculas e espaços antes/depois.

2. KPIs:
- Todos os cards são recalculados depois dos filtros.
- Recebidos usa status_documento exatamente igual a "Recebido".
- Aprovados usa status_documento exatamente igual a "Aprovado".
- Emitidos GRD usa status_grd exatamente igual a "Emitido".

3. Export:
- Usa a mesma função de filtro da tela.
- Inclui caminhos e hyperlinks.

4. Caminhos:
Adicionar no settings.py:

LD_BASE_PATH = r"C:\CAMINHO\DA\PASTA\RAIZ"

A raiz deve ser a pasta que contém:
1 - DOCS EMISSÃO ENGEDOC
9 - PCFs Transpetro
10 - Engenharia

Exemplo:
LD_BASE_PATH = r"C:\Users\daniel.laranjo\Documents\GED_PROFISSIONAL"
