# BESS 5.6.5

## Resumen

Corrección del sync automático cada 15 minutos (cron) y ajuste del preflight de reloj.

## Cambios principales

### Cron — sync automático fiable
- `deploy/install-cron.sh`: el crontab invoca el script con `/usr/bin/env bash` (evita fallos silenciosos al ejecutar el `.sh` directo).
- `scripts/cron_sincronizar.sh`: log `CRON invocado` al inicio; timestamps dinámicos en cada línea del log.
- `docs/DOCKER.md`: tabla de diagnóstico ampliada (cron sin entradas en log, preflight, CRLF).

### Preflight reloj — menos bloqueos falsos
- `scripts/preflight_reloj.py`: solo bloquea con zona incorrecta o NTP **explícitamente** desincronizado; si no puede confirmar NTP (común en VMs Hyper-V), avisa pero permite el sync.
- `bess/data/sync_preflight.py`: distingue mensajes bloqueantes y advertencias en la sidebar admin.

## Migración desde 5.6.4

```bash
cd ~/ReportesBESS
git fetch --tags
git checkout v5.6.5
docker compose up -d --build
bash deploy/install-cron.sh
```

Comprobar (esperar un `:00`, `:15`, `:30` o `:45`):

```bash
grep '^\[' logs/sync-$(date +%Y%m%d).log | tail -3
```

Debe verse `Inicio sync...` seguido de `OK` sin intervención manual.

Si ya corrigió el crontab a mano (`/usr/bin/env bash ...`), `install-cron.sh` lo deja igual.

## Versión anterior

- **5.6.4** — Superadmin, Mantenimiento DB, preflight reloj en cron.
