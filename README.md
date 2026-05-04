# Automacao DocReq - Tempo RRM

Script em Python para:
- abrir o site do projeto;
- autenticar com credenciais do `.env`;
- tentar exportar o relatorio (Excel/CSV);
- fazer fallback para extracao da tabela HTML (com paginacao);
- tratar e padronizar os dados;
- gerar Excel final no formato solicitado.

## Arquivos

- `main.py`
- `.env.example`
- `requirements.txt`

## Requisitos

- Python 3.10+ (recomendado)
- Windows PowerShell (ou terminal equivalente)

## Instalacao

1. Crie e ative ambiente virtual:

```powershell
python -m venv .venv
.venv\Scripts\Activate.ps1
```

2. Instale dependencias:

```powershell
pip install -r requirements.txt
python -m playwright install chromium
```

3. Crie o arquivo `.env` com base no exemplo:

```powershell
copy .env.example .env
```

4. Edite o `.env` com seu usuario/senha e pasta de saida:

```env
SITE_URL=https://tempo-rrm.rrcm.biz/ProjectDashboard/ProjectInformation/25753
USUARIO=seu_usuario_aqui
SENHA=sua_senha_aqui
PASTA_SAIDA=C:\Relatorios\Tempo_RRM
HEADLESS=false
```

## Execucao

```powershell
python main.py
```

## Fluxo implementado

1. `carregar_configuracoes()`
2. `abrir_navegador()`
3. `fazer_login()`
4. `acessar_pagina_projeto()`
5. `localizar_relatorio()`
6. `extrair_dados()`
7. `tratar_dados()`
8. `gerar_excel()`
9. `main()`

## Nome do arquivo gerado

O arquivo final sera salvo como:

`DocReq_Report_Atualizado_YYYY-MM-DD_HH-MM.xlsx`

na pasta definida em `PASTA_SAIDA`.

## Formato da planilha

- Aba: `Table 1`
- Titulo na linha 2
- Cabecalho na linha 3 (A:M)
- Congelamento em `A4`
- Filtro automatico em `A3:M...`
- Ajuste de largura de colunas
- Quebra de texto em `E`, `L`, `M`
- Formato de data (`dd/mm/yyyy`) em `H`, `I`, `J`, `K`
- Bordas leves nas celulas preenchidas
- Cabecalho com fundo azul escuro e fonte branca

## Tratamento de erros

O script gera logs no terminal e trata cenarios como:
- falha de login;
- site fora do ar;
- pagina nao carregada;
- tabela nao encontrada;
- relatorio vazio;
- botao de exportacao nao encontrado;
- erro ao salvar Excel.

## Observacao sobre CAPTCHA/2FA

O script nao tenta burlar mecanismos de seguranca. Se houver autenticacao manual (CAPTCHA/2FA), rode com `HEADLESS=false`, conclua o login no navegador e retorne ao terminal para continuar.
