#!/usr/bin/env bash
# Sync cada 15 min: ION + API + granja -> CSV -> verificar -> filtrar -> reportes.
# Uso manual o desde cron (ver deploy/install-cron.sh).

set -euo pipefail

export PATH="/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin:${PATH:-}"

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
LOG_DIR="$ROOT/logs"
LOCK_FILE="/tmp/bess-sync.lock"
CONTAINER_NAME="bess-app"
mkdir -p "$LOG_DIR"

LOG="$LOG_DIR/sync-$(date +%Y%m%d).log"
TS="$(date '+%Y-%m-%d %H:%M:%S')"

_log() {
  echo "[$TS] $*" >> "$LOG"
}

exec 9>"$LOCK_FILE"
if ! flock -n 9; then
  _log "Omitido: hay otra sincronizacion en curso"
  exit 0
fi

_log "Inicio sync + procesar (usuario=$(whoami), pwd=$ROOT)"

cd "$ROOT"

if ! command -v docker >/dev/null 2>&1; then
  _log "ERROR: comando 'docker' no encontrado (revise PATH del cron)"
  exit 127
fi

if docker compose version >/dev/null 2>&1; then
  DOCKER_COMPOSE=(docker compose)
elif command -v docker-compose >/dev/null 2>&1; then
  DOCKER_COMPOSE=(docker-compose)
else
  _log "ERROR: docker compose no disponible"
  exit 127
fi

_running() {
  docker inspect -f '{{.State.Running}}' "$CONTAINER_NAME" 2>/dev/null | grep -qx true
}

if ! _running; then
  _log "ERROR: contenedor $CONTAINER_NAME no esta en ejecucion"
  "${DOCKER_COMPOSE[@]}" ps >> "$LOG" 2>&1 || true
  exit 1
fi

set +e
"${DOCKER_COMPOSE[@]}" exec -T bess \
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
