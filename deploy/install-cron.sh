#!/usr/bin/env bash
# Instala cron cada 15 minutos en la VM (usuario actual, tipicamente bess).
# Ejecutar desde la raiz del proyecto: bash deploy/install-cron.sh

set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
SYNC_SCRIPT="$ROOT/scripts/cron_sincronizar.sh"
MARKER="cron_sincronizar.sh"

if [ ! -f "$SYNC_SCRIPT" ]; then
  echo "ERROR: no se encuentra $SYNC_SCRIPT" >&2
  exit 1
fi

chmod +x "$SYNC_SCRIPT"
mkdir -p "$ROOT/logs"

CRON_BODY="*/15 * * * * $SYNC_SCRIPT"
CRON_BLOCK=$(
  cat <<EOF
PATH=/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin
CRON_TZ=America/Mexico_City
$CRON_BODY
EOF
)

TMP="$(mktemp)"
{
  crontab -l 2>/dev/null | grep -v "$MARKER" | grep -v '^CRON_TZ=' | grep -v '^PATH=' || true
  echo "$CRON_BLOCK"
} > "$TMP"
crontab "$TMP"
rm -f "$TMP"

echo "Cron instalado (cada 15 minutos, hora Ciudad de Mexico):"
crontab -l | grep -A1 'CRON_TZ' || crontab -l

echo ""
echo "Prueba manual:"
echo "  $SYNC_SCRIPT"
echo "  tail -f $ROOT/logs/sync-\$(date +%Y%m%d).log"
