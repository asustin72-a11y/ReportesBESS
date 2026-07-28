#!/usr/bin/env bash
# Instala cron de Granja cada 15 minutos (servidor Linux).
# Ejecutar desde la raiz del proyecto: bash deploy/install-cron-granja.sh
#
# Conserva otras entradas (p. ej. cron de BESS) y solo actualiza Granja.

set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
SYNC_SCRIPT="$ROOT/scripts/cron_sincronizar_granja.sh"
MARKER="cron_sincronizar_granja.sh"

if [ ! -f "$SYNC_SCRIPT" ]; then
  echo "ERROR: no se encuentra $SYNC_SCRIPT" >&2
  exit 1
fi

chmod +x "$SYNC_SCRIPT"
# LF por si el repo se edito en Windows
if command -v sed >/dev/null 2>&1; then
  sed -i 's/\r$//' "$SYNC_SCRIPT" 2>/dev/null || true
fi
mkdir -p "$ROOT/logs"

CRON_BODY="*/15 * * * * /usr/bin/env bash $SYNC_SCRIPT"

TMP="$(mktemp)"
{
  crontab -l 2>/dev/null | grep -v "$MARKER" | grep -v '^CRON_TZ=' | grep -v '^PATH=' || true
  echo "PATH=/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin"
  echo "CRON_TZ=America/Mexico_City"
  echo "$CRON_BODY"
} > "$TMP"
crontab "$TMP"
rm -f "$TMP"

echo "Cron Granja instalado (cada 15 minutos, America/Mexico_City):"
crontab -l | grep -E 'CRON_TZ|PATH|cron_sincronizar' || crontab -l

echo ""
echo "Prueba manual:"
echo "  $SYNC_SCRIPT"
echo "  tail -f $ROOT/logs/granja-sync-\$(date +%Y%m%d).log"
echo ""
echo "Forzar Python en el host (sin Docker): GRANJA_SYNC_HOST=1 $SYNC_SCRIPT"
