#Requires -Version 5.1
<#
.SYNOPSIS
  Genera dist\descargar_ion.exe con PyInstaller.

.EXAMPLE
  .\scripts\build_descargar_ion.ps1
#>
$ErrorActionPreference = "Stop"
$Root = Split-Path -Parent $PSScriptRoot
Set-Location $Root

Write-Host "Instalando dependencias de build..."
python -m pip install --upgrade pip pyinstaller pymodbus tzdata | Out-Host

$Entry = Join-Path $Root "scripts\descargar_ion_entry.py"
$Dist = Join-Path $Root "dist"
$Build = Join-Path $Root "build"

Write-Host "Compilando descargar_ion.exe..."
python -m PyInstaller `
    --noconfirm `
    --clean `
    --onefile `
    --console `
    --name descargar_ion `
    --paths $Root `
    --hidden-import pymodbus `
    --hidden-import pymodbus.client `
    --hidden-import pymodbus.client.tcp `
    --hidden-import pymodbus.framer `
    --hidden-import pymodbus.framer.socket `
    --hidden-import bess.data.ingest.ion.descargar `
    --hidden-import bess.data.ingest.ion.modbus `
    --hidden-import bess.config.paths `
    --collect-submodules pymodbus `
    --exclude-module streamlit `
    --exclude-module pandas `
    --exclude-module numpy `
    --exclude-module matplotlib `
    --exclude-module plotly `
    --exclude-module playwright `
    --exclude-module reportlab `
    --exclude-module PIL `
    --distpath $Dist `
    --workpath $Build `
    --specpath $Root `
    $Entry

$Exe = Join-Path $Dist "descargar_ion.exe"
if (-not (Test-Path $Exe)) {
    Write-Error "No se genero $Exe"
    exit 1
}

Write-Host ""
Write-Host "Listo: $Exe"
Write-Host "Copie el .exe a la carpeta donde desee ejecutarlo; el CSV se guarda en esa misma carpeta."
