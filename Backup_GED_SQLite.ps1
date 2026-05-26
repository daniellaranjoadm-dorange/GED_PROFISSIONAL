param(
    [int]$RetentionDays = 30
)

$ErrorActionPreference = "Stop"

$DbPath = "C:\GED_DATA\db.sqlite3"
$BackupRoot = "D:\GED_BACKUPS"
$LogPath = Join-Path $BackupRoot "backup_ged.log"

if (!(Test-Path $BackupRoot)) {
    New-Item -ItemType Directory -Path $BackupRoot | Out-Null
}

function Write-Log {
    param([string]$Message)
    $timestamp = Get-Date -Format "yyyy-MM-dd HH:mm:ss"
    Add-Content -Path $LogPath -Value "[$timestamp] $Message"
}

try {
    Write-Log "Iniciando backup do GED."

    if (!(Test-Path $DbPath)) {
        throw "Banco nao encontrado em $DbPath"
    }

    $timestampFile = Get-Date -Format "yyyyMMdd_HHmmss"
    $TempDb = Join-Path $BackupRoot "db.sqlite3"
    $ZipPath = Join-Path $BackupRoot "GED_DB_BACKUP_$timestampFile.zip"

    Copy-Item -Path $DbPath -Destination $TempDb -Force

    if (Test-Path $ZipPath) {
        Remove-Item $ZipPath -Force
    }

    Compress-Archive -Path $TempDb -DestinationPath $ZipPath -Force
    Remove-Item $TempDb -Force

    Write-Log "Backup criado: $ZipPath"

    $Cutoff = (Get-Date).AddDays(-$RetentionDays)

    Get-ChildItem -Path $BackupRoot -Filter "GED_DB_BACKUP_*.zip" |
        Where-Object { $_.LastWriteTime -lt $Cutoff } |
        ForEach-Object {
            Write-Log "Removendo backup antigo: $($_.FullName)"
            Remove-Item $_.FullName -Force
        }

    Write-Log "Backup finalizado com sucesso."
    exit 0
}
catch {
    Write-Log "ERRO: $($_.Exception.Message)"
    exit 1
}
