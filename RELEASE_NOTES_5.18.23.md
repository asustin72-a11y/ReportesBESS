# BESS 5.18.23 — SQLite como fuente de verdad de ArchivosReporte

## Resumen

Los reportes derivados (`COMBINADO_*`, `ENERGIA_*`, `ACUMULADOS_*`, BESS y
generación) viven en `bess_perfiles.db` (`reporte_serie_*`). La UI, CFE y PDF
leen preferentemente de BD; el CSV de `ArchivosReporte` queda como export /
respaldo.

## Cambios

- Módulo `bess/data/report_store.py` + esquema en `init_db`
- Escritores duales en aggregates (`combined`, `daily`, `accumulated`, `bess_daily`, `granja`)
- Lectores BD-preferente en `pages`, CFE, generación y PDF
- Fallback CSV desactivado por defecto (`BESS_REPORTES_FALLBACK_CSV=0`)
- Script `scripts/importar_reportes_sqlite.py` para bootstrapping
- Docs Fase 7 en `bess/PLAN_MIGRACION_SQLITE.md`
- Tests `tests/test_report_store.py`

## Migración desde 5.18.22

```bash
cd ~/ReportesBESS
git fetch --tags
git checkout -f v5.18.23
docker compose up -d --build
docker compose exec -T bess python scripts/importar_reportes_sqlite.py
```

El import one-shot carga los CSV existentes a BD (en producción ya corrido:
34 series / ~410k filas). El cron `--procesar` sigue actualizando CSV y tablas.

### Variables opcionales

| Variable | Default | Uso |
|----------|---------|-----|
| `BESS_REPORTES_ESCRIBIR_CSV` | `1` | Seguir escribiendo CSV de respaldo |
| `BESS_REPORTES_FALLBACK_CSV` | `0` | Leer CSV si no hay filas en BD |
| `BESS_REPORTES_SOLO_BD` | — | Forzar solo BD |
