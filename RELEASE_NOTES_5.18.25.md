# BESS 5.18.25 — SQLite reportes + leyenda + fix dtypes

## Resumen

Release de integración: ArchivosReporte en SQLite (Fase 7), toggle de leyenda
en gráficas y corrección de tipos numéricos al leer de BD (evita el error
`agg function failed [how->max,dtype->object]` en el dashboard).

## Cambios (desde 5.18.22)

### Fase 7 — SQLite fuente de verdad de reportes
- Tablas `reporte_serie_*` en `bess_perfiles.db`
- Escritores duales (BD + CSV) y lectores BD-preferente en UI/CFE/PDF
- `scripts/importar_reportes_sqlite.py` para bootstrapping
- CSV de `ArchivosReporte` como export/respaldo (`BESS_REPORTES_ESCRIBIR_CSV`)

### UX gráficas
- Toggle de leyenda Plotly rehabilitado (`itemclick=toggle`)

### Fix
- Coerción a numérico al cargar series desde JSON (celdas vacías ya no dejan
  columnas `object` que rompen `groupby().max()` en perfil multidía)

## Migración desde 5.18.22–5.18.24

```bash
cd ~/ReportesBESS
git fetch --tags
git checkout -f v5.18.25
docker compose up -d --build
```

Si aún no importaste reportes a BD (primera vez en Fase 7):

```bash
docker compose exec -T bess python scripts/importar_reportes_sqlite.py
```

Si ya importaste en 5.18.23+, **no** hace falta reimportar.
