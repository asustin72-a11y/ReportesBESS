#!/usr/bin/env bash
# Instala cron horario para actualizar tarifas BESS desde CFE.
# Uso: sudo bash deploy/install-cron-tarifas-bess.sh

set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
SCRIPT="$ROOT/scripts/cron_actualizar_tarifas_bess.sh"
MARKER="# bess-tarifas-cfe"

if [[ ! -x "$SCRIPT" ]]; then
  chmod +x "$SCRIPT" || true
fi

LINE="0 * * * * TZ=America/Mexico_City $SCRIPT $MARKER"

TMP="$(mktemp)"
crontab -l 2>/dev/null | grep -v "$MARKER" >"$TMP" || true
echo "$LINE" >>"$TMP"
crontab "$TMP"
rm -f "$TMP"

echo "Cron instalado:"
echo "  $LINE"
echo "El script espera al día 1 ≥ 02:00 y reintenta cada hora si CFE aún no publica."
