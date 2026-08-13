# BESS 5.18.14 — Aspecto original de gráficas

## Resumen

Restaura el aspecto visual previo de las gráficas (rellenos y hover unificado)
manteniendo la protección anti-cuelgue: **leyenda no clicable**.

## Cambios

- Perfil / generación / análisis: vuelven `fill='tozeroy'` y `hovermode='x unified'`
- Sin selector “Series visibles” en el perfil
- Sigue sin poder ocultar series con clic en la leyenda (evita colgar Streamlit)

## Migración desde 5.18.13

```bash
cd ~/ReportesBESS
git fetch --tags
git checkout -f v5.18.14
docker compose up -d --build
```
