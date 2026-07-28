# Sync Granja cada 15 min — solo desarrollo local en Windows.
# En servidor Linux use: scripts/cron_sincronizar_granja.sh
#   bash deploy/install-cron-granja.sh
#
# Programar con Task Scheduler o:
#   powershell -ExecutionPolicy Bypass -File scripts\cron_sincronizar_granja.ps1

$ErrorActionPreference = "Stop"
$Root = Split-Path -Parent (Split-Path -Parent $MyInvocation.MyCommand.Path)
$LogDir = Join-Path $Root "logs"
New-Item -ItemType Directory -Force -Path $LogDir | Out-Null
$Log = Join-Path $LogDir ("granja-sync-{0:yyyyMMdd}.log" -f (Get-Date))

function Write-Log([string]$Message) {
    $ts = Get-Date -Format "yyyy-MM-dd HH:mm:ss"
    Add-Content -Path $Log -Value "[$ts] $Message"
}

Write-Log "CRON Granja (Windows local) invocado (pid=$PID)"
Set-Location $Root

$python = Get-Command python -ErrorAction SilentlyContinue
if (-not $python) {
    Write-Log "ERROR: python no encontrado en PATH"
    exit 127
}

& $python.Source scripts\sincronizar_granja_megas.py --quiet *>> $Log
$rc = $LASTEXITCODE
if ($rc -eq 0) {
    Write-Log "OK"
} else {
    Write-Log "ERROR (codigo $rc)"
}
exit $rc
