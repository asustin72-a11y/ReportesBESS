#!/usr/bin/env bash
# Sync horario: ION + API + granja -> CSV -> verificar -> filtrar -> reportes.
# Uso manual o desde cron (ver deploy/install-cron.sh).

set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
LOG_DIR="$ROOT/logs"
LOCK_FILE="/tmp/bess-sync.lock"
mkdir -p "$LOG_DIR"

LOG="$LOG_DIR/sync-$(date +%Y%m%d).log"
TS="$(date '+%Y-%m-%d %H:%M:%S')"

exec 9>"$LOCK_FILE"
if ! flock -n 9; then
  echo "[$TS] Omitido: hay otra sincronizacion en curso" >> "$LOG"
  exit 0
fi

echo "[$TS] Inicio sync + procesar" >> "$LOG"

cd "$ROOT"

if ! docker compose ps --status running --services 2>/dev/null | grep -qx 'bess'; then
  echo "[$TS] ERROR: contenedor bess no esta en ejecucion" >> "$LOG"
  exit 1
fi

set +e
docker compose exec -T bess \
  python scripts/sincronizar_perfiles.py --quiet --procesar >> "$LOG" 2>&1
RC=$?
set -e

TS_END="$(date '+%Y-%m-%d %H:%M:%S')"
if [ "$RC" -eq 0 ]; then
  echo "[$TS_END] OK" >> "$LOG"
else
  echo "[$TS_END] ERROR (codigo $RC)" >> "$LOG"
  exit "$RC"
fi
