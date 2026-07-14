#Requires -Version 5.1
<#
.SYNOPSIS
  Descarga perfil de carga de un medidor ION hasta el ultimo registro disponible.

.DESCRIPTION
  Conecta por Modbus TCP, lee el Data Recorder y guarda un CSV en la carpeta
  desde la que se ejecuta el script (o en la ruta indicada). Si la fecha de inicio
  es anterior al primer registro del medidor, muestra un aviso y descarga todos
  los datos disponibles.

.PARAMETER Ip
  Direccion IP del medidor ION.

.PARAMETER Desde
  Fecha de inicio (YYYY-MM-DD o YYYY-MM-DD HH:MM:SS).

.PARAMETER Salida
  Ruta opcional del archivo CSV de salida.

.EXAMPLE
  .\scripts\descargar_ion.ps1 -Ip 172.16.111.209 -Desde 2026-05-01

.EXAMPLE
  .\scripts\descargar_ion.ps1 172.16.111.209 2026-05-01 data\ArchivosFuente\ion.csv
#>
param(
    [Parameter(Mandatory = $true, Position = 0)]
    [string]$Ip,

    [Parameter(Mandatory = $true, Position = 1)]
    [string]$Desde,

    [Parameter(Mandatory = $false, Position = 2)]
    [string]$Salida
)

$ErrorActionPreference = "Stop"
$Root = Split-Path -Parent $PSScriptRoot
$Script = Join-Path $Root "scripts\descargar_ion.py"

if (-not (Test-Path $Script)) {
    Write-Error "No se encontro $Script"
    exit 1
}

$Python = Get-Command python -ErrorAction SilentlyContinue
if (-not $Python) {
    Write-Error "Python no encontrado en PATH"
    exit 1
}

$Args = @($Script, $Ip, $Desde)
if ($Salida) {
    $Args += $Salida
}

& $Python.Source @Args
exit $LASTEXITCODE
