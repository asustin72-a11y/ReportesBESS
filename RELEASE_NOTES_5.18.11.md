# BESS 5.18.11 — Barra de progreso en rebuild total

## Resumen

El **Rebuild total desde BD** muestra barra de avance (export por medidor →
borrado CSV → Verificar → Filtrar → Reportes).

## Migración desde 5.18.10

```bash
cd ~/ReportesBESS
git fetch --tags
git checkout -f v5.18.11
docker compose up -d --build
```
