# Sincroniza parches post-v5.6.0 (Generación Acumulada + logout limpio) a la VM.
# Uso: .\deploy\actualizar-ui-vm.ps1
# Requiere: scp/ssh en PATH y acceso a bess@172.16.208.250

$ErrorActionPreference = "Stop"
$HostVM = "bess@172.16.208.250"
$RemoteRoot = "~/ReportesBESS"
$LocalRoot = Split-Path -Parent $PSScriptRoot

$files = @(
    @{ Local = "bess\ui\pages.py"; Remote = "bess/ui/pages.py" },
    @{ Local = "bess\ui\auth.py"; Remote = "bess/ui/auth.py" },
    @{ Local = "bess\ui\sidebar.py"; Remote = "bess/ui/sidebar.py" },
    @{ Local = "bess\ui\styles.py"; Remote = "bess/ui/styles.py" },
    @{ Local = "bess\reports\daily_pdf.py"; Remote = "bess/reports/daily_pdf.py" },
    @{ Local = "bess\reports\accumulated_pdf.py"; Remote = "bess/reports/accumulated_pdf.py" },
    @{ Local = "bess\data\aggregates\generacion.py"; Remote = "bess/data/aggregates/generacion.py" },
    @{ Local = "bess\config\subestaciones.py"; Remote = "bess/config/subestaciones.py" }
)

Write-Host "Origen: $LocalRoot"
Write-Host "Destino: ${HostVM}:${RemoteRoot}"
Write-Host ""

foreach ($f in $files) {
    $src = Join-Path $LocalRoot $f.Local
    if (-not (Test-Path $src)) {
        throw "No existe: $src"
    }
    $dest = "${HostVM}:${RemoteRoot}/$($f.Remote)"
    Write-Host "scp $src -> $dest"
    scp $src $dest
}

Write-Host ""
Write-Host "Copiando archivos al contenedor bess-app..."
foreach ($f in $files) {
    $remoteHost = "$RemoteRoot/$($f.Remote)"
    $containerPath = "/app/$($f.Remote)"
    Write-Host "docker cp $remoteHost -> bess-app:$containerPath"
    ssh $HostVM "docker cp $remoteHost bess-app:$containerPath"
}

Write-Host ""
Write-Host "Reiniciando contenedor..."
ssh $HostVM "cd $RemoteRoot && docker compose restart bess"

Write-Host ""
Write-Host "Listo. Verifique:"
Write-Host "  - PDF acumulado: Día Tipo sin fecha (solo kWh arriba de la gráfica)"
Write-Host "  - Cerrar sesion: pantalla de login sin restos de sidebar"
