$ErrorActionPreference = "Stop"

$py = ".\venv\Scripts\python.exe"
if (!(Test-Path $py)) { $py = "python" }

Write-Host "== GED TEST: compileall (apps + ged) =="
$exclude = "^\.(?:\\|/)(?:\.git|venv|\.venv|media|staticfiles|Docs|scripts|tools|tmp|temp)(?:\\|/)|(?:\\|/)(?:_Backup|Backup|_backup)(?:\\|/)|(?:\\|/)old(?:\\|/)|(?:\\|/)\.pytest_cache(?:\\|/)|(?:\\|/)__pycache__(?:\\|/)"
& $py -m compileall .\ged .\apps -q -x $exclude | Out-Host

Write-Host "== GED TEST: django check =="
& $py manage.py check | Out-Host

Write-Host "== GED TEST: migrations check (dry) =="
& $py manage.py makemigrations --check --dry-run | Out-Host

Write-Host "== GED TEST: url reverse smoke =="
$one = "from django.urls import reverse; names=['set_language','logout','contas:minhas_configuracoes','contas:usuarios_permissoes','solicitacoes:listar_solicitacoes','documentos:listar_documentos','documentos:upload_documento','documentos:importar_ldp','documentos:painel_workflow','documentos:medicao','documentos:lixeira']; [reverse(n) for n in names]; print('GED_TEST_OK')"
& $py manage.py shell -c $one | Out-Host

Write-Host "== GED TEST: charset smoke (templates) =="
$bad = Get-ChildItem -Path .\apps -Recurse -Filter *.html | Where-Object { $_.FullName -like "*\templates\*" } | Select-String -Pattern '\?{2,}' -AllMatches
if ($bad) {
    $bad | ForEach-Object { Write-Host "$($_.Path):$($_.LineNumber):$($_.Line)" }
    exit 1
} else {
    Write-Host "CHARSET_OK"
}

Write-Host "== GED TEST: OK =="
