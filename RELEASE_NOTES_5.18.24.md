# BESS 5.18.24 — Toggle de leyenda en gráficas Plotly

## Resumen

Se rehabilita el clic en la leyenda (mostrar/ocultar series) en BESS,
Análisis de Perfil y Granja. Antes estaba desactivado por un cuelgue
histórico de Streamlit; el saneo de figuras vuelve a forzar `toggle`.

## Cambios

- `bess/charts/layout.py`: `itemclick=toggle` / `itemdoubleclick=toggleothers`
- `analisis_perfil/ui/pages.py`: mismas opciones en gráficas propias
- Tests actualizados en `tests/test_chart_title_legend_spacing.py`

## Migración desde 5.18.23

```bash
cd ~/ReportesBESS
git fetch --tags
git checkout -f v5.18.24
docker compose up -d --build
```
