# Genera ZIP portable de la Suite IUSASOL para otra computadora.
# Uso: .\scripts\crear_respaldo.ps1
#      .\scripts\crear_respaldo.ps1 -SinSecretos   # sin .env ni secrets.toml
# Salida: backups\BESS_vX.Y.Z_respaldo_YYYY-MM-DD.zip

param(
    [switch]$SinSecretos
)

$ErrorActionPreference = "Stop"
$root = Split-Path -Parent (Split-Path -Parent $MyInvocation.MyCommand.Path)
Set-Location $root

$version = (Select-String -Path "bess\__init__.py" -Pattern '__version__ = "([^"]+)"').Matches.Groups[1].Value
$fecha = Get-Date -Format "yyyy-MM-dd"
$backupsDir = Join-Path $root "backups"
$zipName = "BESS_v${version}_respaldo_${fecha}.zip"
$zipPath = Join-Path $backupsDir $zipName
$staging = Join-Path $backupsDir "_staging_respaldo"

if (Test-Path $staging) { Remove-Item $staging -Recurse -Force }
New-Item -ItemType Directory -Path $staging -Force | Out-Null
New-Item -ItemType Directory -Path $backupsDir -Force | Out-Null

$excludeDirs = @(
    "__pycache__", ".git", ".venv", "venv", "env",
    "build", "dist", "backups", ".cursor", ".devcontainer"
)
$robocopyExcludeFiles = @(
    "*.pyc", "*.pyo",
    "_pages_189.py",
    "_test_*.pdf",
    "_cache_geo_*.json"
)
if ($SinSecretos) {
    $robocopyExcludeFiles += @(".env", "secrets.toml")
}

Write-Host "Copiando proyecto a staging ($staging)..."
if (-not $SinSecretos) {
    Write-Host "Incluye secretos (.env, .streamlit\secrets.toml) - guarda el ZIP en lugar seguro."
}
Get-ChildItem -Path $root -Force | ForEach-Object {
    if ($excludeDirs -contains $_.Name) { return }
    if ($_.Name -eq "backups") { return }
    if ($_.Name -eq "_pages_189.py") { return }
    if ($_.Name -like "_test_*.pdf") { return }

    if ($_.PSIsContainer) {
        $dest = Join-Path $staging $_.Name
        $robocopyArgs = @(
            $_.FullName, $dest,
            "/E",
            "/XD", "__pycache__", ".git", ".venv", "venv", "env", "build", "dist", "backups", ".cursor",
            "analisis_perfil_trabajo",
            "/XF") + $robocopyExcludeFiles + @("/NFL", "/NDL", "/NJH", "/NJS", "/nc", "/ns", "/np")
        & robocopy @robocopyArgs | Out-Null
        if ($LASTEXITCODE -ge 8) { throw "robocopy fallo con codigo $LASTEXITCODE" }
    } else {
        Copy-Item $_.FullName (Join-Path $staging $_.Name) -Force
    }
}

# Asegurar carpeta fuente vacia con marcador
$fuente = Join-Path $staging "data\ArchivosFuente"
if (-not (Test-Path $fuente)) { New-Item -ItemType Directory -Path $fuente -Force | Out-Null }
$gitkeep = Join-Path $fuente ".gitkeep"
if (-not (Test-Path $gitkeep)) { Set-Content -Path $gitkeep -Value "" -Encoding UTF8 }

if (Test-Path $zipPath) { Remove-Item $zipPath -Force }
Write-Host "Comprimiendo -> $zipPath"
Compress-Archive -Path (Join-Path $staging "*") -DestinationPath $zipPath -CompressionLevel Optimal

Remove-Item $staging -Recurse -Force

$sizeMb = [math]::Round((Get-Item $zipPath).Length / 1MB, 2)
Write-Host ""
Write-Host "Listo: $zipPath (${sizeMb} MB)"
Write-Host "Descomprime en la otra PC y sigue RESTAURACION_LOCAL.md"
