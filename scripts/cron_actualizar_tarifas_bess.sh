#!/usr/bin/env bash
# Actualización automática de tarifas BESS (DIST/GDMTH) desde CFE.
# Cron recomendado (hora México): cada hora; el script espera al día 1 02:00
# y reintenta mientras el mes no esté publicado.
#
#   0 * * * * /ruta/ReporteadorIUSASOL/scripts/cron_actualizar_tarifas_bess.sh

set -euo pipefail

export PATH="/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin:${PATH:-}"
export TZ="${TZ:-America/Mexico_City}"

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
LOG_DIR="$ROOT/logs"
LOCK_FILE="/tmp/bess-tarifas-cfe.lock"
CONTAINER_NAME="bess-app"
mkdir -p "$LOG_DIR"

LOG="$LOG_DIR/tarifas-cfe-$(date +%Y%m%d).log"

_log() {
  echo "[$(date '+%Y-%m-%d %H:%M:%S')] $*" >> "$LOG"
}

_log "CRON tarifas CFE (pid=$$)"

exec 9>"$LOCK_FILE"
if ! flock -n 9; then
  _log "Omitido: otra actualización de tarifas en curso"
  exit 0
fi

cd "$ROOT"

if command -v docker >/dev/null 2>&1 && docker inspect -f '{{.State.Running}}' "$CONTAINER_NAME" 2>/dev/null | grep -qx true; then
  _log "Ejecutando dentro de $CONTAINER_NAME"
  set +e
  docker exec "$CONTAINER_NAME" python scripts/actualizar_tarifas_bess_mes.py >>"$LOG" 2>&1
  RC=$?
  set -e
else
  _log "Ejecutando en host (python3)"
  set +e
  python3 "$ROOT/scripts/actualizar_tarifas_bess_mes.py" >>"$LOG" 2>&1
  RC=$?
  set -e
fi

_log "Fin tarifas CFE (exit=$RC)"
exit "$RC"
