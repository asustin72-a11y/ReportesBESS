# BESS 5.18.21 — Demanda por periodo y filtro de fechas (Análisis de Perfil)

## Resumen

En **Análisis de Perfil**, para tarifas horarias con demanda (DIST / GDMTH) se
calcula la **demanda máxima por periodo** (Base / Intermedio / Punta). Además se
corrige el filtro de subintervalo para que no permita fechas fuera del perfil.

## Cambios

- Demanda máxima por periodo con media rodante CFE 15 min (misma lógica BESS)
- Tabla en Resumen + inclusión en el PDF del análisis
- Filtro de fechas: Desde/Hasta acotados al rango detectado del archivo
- Caption del rango en DD/MM/YYYY y aviso del subintervalo efectivo

## Migración desde 5.18.20

```bash
cd ~/ReportesBESS
git fetch --tags
git checkout -f v5.18.21
docker compose up -d --build
```
