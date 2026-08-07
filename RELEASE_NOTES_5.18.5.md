# BESS 5.18.5 — Suite IUSASOL

## Resumen

Release de **toda la suite** en `main`: BESS, Granja, Descargas, **Análisis de Perfil** y **Consultar Tarifa**, con versión visible **v5.18.5** en cada app. Incluye el formateo de tablas de Granja (kWh / `$`).

## Apps hermanas

| App | Entry |
|-----|-------|
| BESS | `streamlit_app.py` / `streamlit_bess.py` / Suite |
| Granja Solar | `streamlit_granja.py` |
| Descargas API | `streamlit_descargas.py` |
| Análisis de Perfil | `streamlit_analisis_perfil.py` |
| Consultar Tarifa | `streamlit_tarifas_cfe.py` |

Portal: `suite/` (BESS · Granja · Descargas). Análisis y Consultar Tarifa corren con entry propio (mismo login BESS).

## Cambios en este tag

- Tablas Granja: miles, `$` en ingresos, unidades en encabezados (`granja/ui/pages.py`)
- Versión `v5.18.5` visible en header/sidebar de las hermanas
- Paquete `analisis_perfil/` + catálogo T01/DIST/GDMTH
- Paquete `tarifas_cfe/` (consulta CFE + reportes CSV)
- Cliente CFE Playwright: `bess/data/ingest/cfe/`
- Scripts/cron tarifas: `scripts/reporte_tarifas_cfe.py`, `deploy/install-cron-tarifas-bess.sh`
- Semillas `Tarifas_T1_2026.csv` / `Tarifas_PDBT_2026.csv` y `data/ReportesTarifasCFE/`
- Imagen Compose: `bess:5.18.5`

## Migración desde 5.18.4 (o 5.14.0)

```bash
cd ~/ReportesBESS
git fetch --tags
git checkout -f v5.18.5
# cron granja / tarifas si aplica (LF):
sed -i 's/\r$//' scripts/cron_sincronizar_granja.sh deploy/install-cron-granja.sh \
  scripts/cron_actualizar_tarifas_bess.sh deploy/install-cron-tarifas-bess.sh 2>/dev/null || true
docker compose up -d --build
grep __version__ bess/__init__.py
```

Apps hermanas (mismo clone):

```bash
streamlit run streamlit_granja.py
streamlit run streamlit_descargas.py
streamlit run streamlit_analisis_perfil.py
streamlit run streamlit_tarifas_cfe.py
```
