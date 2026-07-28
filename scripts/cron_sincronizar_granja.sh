#!/usr/bin/env bash
# Sync Granja cada 15 min: 21 MEGAs (API Farm → SQLite).
# Destino operativo: servidor Linux (cron). Ver deploy/install-cron-granja.sh.
#
# Preferencia:
#   1) docker compose exec en contenedor bess-app (mismo data/secrets que BESS)
#   2) python3 en el host (venv .venv si existe)
# Forzar host: GRANJA_SYNC_HOST=1 bash scripts/cron_sincronizar_granja.sh

set -euo pipefail

export PATH="/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin:${PATH:-}"

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
LOG_DIR="$ROOT/logs"
LOCK_FILE="/tmp/granja-sync.lock"
CONTAINER_NAME="${GRANJA_CONTAINER_NAME:-bess-app}"
SERVICE_NAME="${GRANJA_COMPOSE_SERVICE:-bess}"
mkdir -p "$LOG_DIR"

LOG="$LOG_DIR/granja-sync-$(date +%Y%m%d).log"

_log() {
  echo "[$(date '+%Y-%m-%d %H:%M:%S')] $*" >> "$LOG"
}

_log "CRON Granja invocado (pid=$$, usuario=$(whoami), shell=$0)"

exec 9>"$LOCK_FILE"
if ! flock -n 9; then
  _log "Omitido: hay otra sincronizacion Granja en curso (flock)"
  exit 0
fi

_log "Inicio sync MEGAs (pwd=$ROOT)"
cd "$ROOT"

PREFLIGHT_JSON="$ROOT/data/sync_preflight_granja.json"
if ! python3 "$ROOT/scripts/preflight_reloj.py" "$PREFLIGHT_JSON"; then
  _log "BLOQUEO: preflight reloj/zona — sync automatico omitido (ver data/sync_preflight_granja.json)"
  exit 1
fi

_run_host() {
  local py=python3
  if [ -x "$ROOT/.venv/bin/python" ]; then
    py="$ROOT/.venv/bin/python"
  elif [ -x "$ROOT/venv/bin/python" ]; then
    py="$ROOT/venv/bin/python"
  fi
  _log "Ejecutando en host: $py scripts/sincronizar_granja_megas.py --quiet"
  set +e
  "$py" scripts/sincronizar_granja_megas.py --quiet >> "$LOG" 2>&1
  return $?
}

_run_docker() {
  local compose
  if docker compose version >/dev/null 2>&1; then
    compose=(docker compose)
  elif command -v docker-compose >/dev/null 2>&1; then
    compose=(docker-compose)
  else
    return 127
  fi

  if ! docker inspect -f '{{.State.Running}}' "$CONTAINER_NAME" 2>/dev/null | grep -qx true; then
    _log "Contenedor $CONTAINER_NAME no esta en ejecucion"
    return 1
  fi

  _log "Ejecutando en Docker: ${compose[*]} exec -T $SERVICE_NAME python scripts/sincronizar_granja_megas.py --quiet"
  set +e
  "${compose[@]}" exec -T "$SERVICE_NAME" \
    python scripts/sincronizar_granja_megas.py --quiet >> "$LOG" 2>&1
  return $?
}

RC=1
if [ "${GRANJA_SYNC_HOST:-0}" = "1" ]; then
  _run_host
  RC=$?
elif command -v docker >/dev/null 2>&1; then
  if _run_docker; then
    RC=0
  else
    docker_rc=$?
    if [ "$docker_rc" -eq 127 ]; then
      _log "Docker compose no disponible; intento host"
      _run_host
      RC=$?
    else
      RC=$docker_rc
    fi
  fi
else
  _log "Docker no encontrado; ejecutando en host"
  _run_host
  RC=$?
fi

set -e
if [ "$RC" -eq 0 ]; then
  _log "OK"
else
  _log "ERROR (codigo $RC)"
  exit "$RC"
fi
