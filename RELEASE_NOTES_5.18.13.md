# BESS 5.18.13 — Catálogo usable y gráficas sin cuelgue

## Resumen

Corrige el alta de medidores en el editor de catálogo (filas que “no
aceptaban” el valor) y evita que el navegador se cuelgue al interactuar
con leyendas Plotly en BESS, Granja y Análisis de perfil.

## Cambios

### Catálogo
- Con filtro por subestación, las filas nuevas conservan la subestación
- Tipo/Descarga como selectores de texto (sin `"nan"` en celdas vacías)
- Limpieza de celdas vacías al validar/guardar

### Gráficas (suite)
- Leyenda Plotly **no clicable** (clics congelaban Streamlit)
- Helper `sanear_figura_plotly` en todo `st.plotly_chart` (BESS, Granja, Análisis)
- Perfil de carga: selector Streamlit **Series visibles**
- Hover seguro (`closest`); menos rellenos `tozeroy`

## Migración desde 5.18.12

```bash
cd ~/ReportesBESS
git fetch --tags
git checkout -f v5.18.13
docker compose up -d --build
```
