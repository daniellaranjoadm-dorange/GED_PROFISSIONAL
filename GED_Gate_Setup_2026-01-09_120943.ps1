# GED_Gate_Setup.ps1
# Instala/atualiza o pre-commit gate (Windows) para o projeto GED_PROFISSIONAL.
# Uso (na raiz do projeto):
#   powershell -ExecutionPolicy Bypass -File .\GED_Gate_Setup.ps1
# Obs: por segurança, este script NÃO remove arquivos já trackeados no Git.

param(
  [string]$ProjectRoot = (Get-Location).Path,
  [switch]$UpdateGitignore = $true
)

$ErrorActionPreference = "Stop"

function Ensure-Dir($p) {
  if (!(Test-Path $p)) { New-Item -ItemType Directory -Force $p | Out-Null }
}

function Backup-IfExists($path) {
  if (Test-Path $path) {
    $ts = Get-Date -Format "yyyyMMdd_HHmmss"
    Copy-Item $path "$path.bak_$ts" -Force
  }
}

Write-Host "== GED Gate Setup =="
Write-Host "ProjectRoot: $ProjectRoot"

if (!(Test-Path (Join-Path $ProjectRoot ".git"))) {
  throw "Nao encontrei .git em $ProjectRoot. Rode na raiz do repo (onde fica manage.py e a pasta .git)."
}

$hooks = Join-Path $ProjectRoot ".git\hooks"
Ensure-Dir $hooks

$preCommit = Join-Path $hooks "pre-commit"
$preCommitPs1 = Join-Path $hooks "pre-commit.ps1"

Backup-IfExists $preCommit
Backup-IfExists $preCommitPs1

# 1) Launcher (pre-commit) - ASCII sem BOM
$launcher = @'
#!/bin/sh
powershell -ExecutionPolicy Bypass -File ".git/hooks/pre-commit.ps1"
exit $?
'@
$launcher | Set-Content -Encoding Ascii -NoNewline $preCommit

# 2) Gate (pre-commit.ps1)
$gate = @'
$ErrorActionPreference = "Stop"

$py = ".\venv\Scripts\python.exe"
if (!(Test-Path $py)) { $py = "python" }

Write-Host "== GED GATE: compileall (apps ativos, ignorando backups/lixo) =="

$exclude = "^\.(?:\\|/)(?:\.git|venv|\.venv|media|staticfiles|Docs|scripts|tools|tmp|temp)(?:\\|/)|(?:\\|/)(?:_Backup|Backup|_backup)(?:\\|/)|(?:\\|/)old(?:\\|/)|(?:\\|/)\.pytest_cache(?:\\|/)|(?:\\|/)__pycache__(?:\\|/)"

& $py -m compileall `
  .\ged `
  .\apps\contas `
  .\apps\documentos `
  .\apps\dashboard `
  .\apps\solicitacoes `
  .\manage.py `
  -q -x $exclude | Out-Host

Write-Host "== GED GATE: django check =="
& $py manage.py check | Out-Host

Write-Host "== GED GATE: url reverse smoke =="
$one = "from django.urls import reverse; names=['set_language','logout','contas:minhas_configuracoes','contas:usuarios_permissoes','solicitacoes:listar_solicitacoes','documentos:listar_documentos','documentos:upload_documento','documentos:importar_ldp','documentos:painel_workflow','documentos:medicao','documentos:lixeira']; [reverse(n) for n in names]; print('URL_REVERSE_OK')"
& $py manage.py shell -c $one | Out-Host

Write-Host "== GED GATE: OK (commit liberado) =="
exit 0
'@
$gate | Set-Content -Encoding UTF8 -NoNewline $preCommitPs1

Write-Host "Hooks atualizados:"
Write-Host " - $preCommit"
Write-Host " - $preCommitPs1"

# 3) Opcional: atualizar .gitignore (append se faltarem linhas)
if ($UpdateGitignore) {
  $gi = Join-Path $ProjectRoot ".gitignore"
  if (Test-Path $gi) {
    $content = Get-Content $gi -Raw
    $appendBlock = @'

# GED Gate - extras recomendados (backups/zips/old)
*.bak_*
*.before_*
*.zip
static/css/old/
static/**/old/
'@
    if ($content -notmatch "GED Gate - extras recomendados") {
      Add-Content -Path $gi -Value $appendBlock
      Write-Host ".gitignore atualizado (bloco GED Gate adicionado)."
    } else {
      Write-Host ".gitignore ja contem o bloco GED Gate (ok)."
    }
  } else {
    Write-Host "Aviso: .gitignore nao encontrado."
  }
}

Write-Host "== Setup concluido =="
Write-Host "Teste: git commit -m ""teste gate"" --allow-empty"
