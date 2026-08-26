# BESS 5.18.19 — Fechas DD/MM/YYYY en date pickers

## Resumen

Fija el formato de `st.date_input` a **DD/MM/YYYY** en BESS, Descargas y
herramientas DB. El default de Streamlit (`YYYY/MM/DD`) quedó visible tras el
rebuild limpio con Streamlit 1.62.

## Cambios

- `format="DD/MM/YYYY"` en selectores Desde/Hasta (reporteador, generación,
  componentes, Mantenimiento DB, Descargas, bridge Análisis)

## Migración desde 5.18.18

```bash
cd ~/ReportesBESS
git fetch --tags
git checkout -f v5.18.19
docker compose up -d --build
```
