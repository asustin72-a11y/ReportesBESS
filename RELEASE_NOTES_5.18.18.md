# BESS 5.18.18 — Shapley kW precisos y aviso de reporte sin falso positivo

## Resumen

La aportación Shapley por participante se muestra con 3 decimales (el total
N−∅ sigue en enteros CFE). El aviso de reporte desactualizado ya no salta
cuando el COMBINADO está al día con el filtrado aunque `sync_state` vaya
más adelante.

## Cambios

- Shapley: `redondear_kw(..., 3)` por participante (UI, acumulado y PDF)
- Aviso de desfase: tope = `min(sync_state, última Fecha del filtrado)`
- Invalidación de caché del aviso tras Filtrar / Generar reportes / Procesar todo
- Pruebas de desfase ampliadas (falso positivo sync vs filtrado)

## Migración desde 5.18.17

```bash
cd ~/ReportesBESS
git fetch --tags
git checkout -f v5.18.18
docker compose up -d --build
```
