# BESS 5.6.3

## Resumen

Corrección crítica del sync automático con cogeneración IUSA 1 y mejoras de robustez del cron Docker.

## Cambios principales

### Corrección — reportes de cogeneración
- `bess/data/aggregates/granja.py`: el agregado diario usaba `KWH_REC` fijo en el `pivot_table` aunque cogeneración trabaja con `KWH_ENT`.
- Síntoma: `KeyError: 'KWH_REC'` al final de `sincronizar_perfiles.py --procesar`; el cron fallaba y `Validado` no se actualizaba.

### Cron Docker más robusto
- `scripts/cron_sincronizar.sh`: `PATH` explícito, detección de `docker compose` / `docker-compose`, verificación del contenedor `bess-app` vía `docker inspect`, mensajes de log más claros.
- `deploy/install-cron.sh`: incluye `PATH` en la entrada de crontab.
- `docs/DOCKER.md`: tabla de diagnóstico para sync automático.

## Migración desde 5.6.2

```bash
cd ~/ReportesBESS
git fetch --tags
git checkout v5.6.3
docker compose up -d --build
bash deploy/install-cron.sh
bash scripts/cron_sincronizar.sh
```

Comprobar: `tail -5 logs/sync-$(date +%Y%m%d).log` debe terminar en `OK`.

## Versión anterior

- **5.6.2** — Reporte acumulado, Día Tipo, participación Shapley mejorada.
