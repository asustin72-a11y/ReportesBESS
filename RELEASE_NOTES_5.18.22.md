# BESS 5.18.22 — Sync manual de tarifas CFE y protección de catálogo

## Resumen

En **Catálogo → Tarifas** se puede forzar la sincronización desde CFE cuando
la publicación llega tarde y el cron no actualizó. Además, un sync ya no pisa
meses/tipos con precio cargado usando ceros o respuestas parciales.

## Cambios

- Botón **Sincronizar** (esquema actual o las 4) con año/mes en el admin de tarifas
- Persistencia unificada: CSV + `catalog_tarifas` + `catalog_tarifas_hist`
- Fusión CSV∪BD: un `0` no sobrescribe un valor `> 0`
- `publicado()` exige energía/capacidad (no basta solo CargoFijo)
- CLI (`actualizar_tarifas_bess_mes` / `consultar_tarifas_cfe`) usa el mismo camino seguro
- Tests de protección en `tests/test_tarifas_proteccion.py`

## Migración desde 5.18.21

```bash
cd ~/ReportesBESS
git fetch --tags
git checkout -f v5.18.22
docker compose up -d --build
```

Tras el rebuild, si agosto quedó en 0: Catálogo → Tarifas → mes 8 → Sincronizar.
