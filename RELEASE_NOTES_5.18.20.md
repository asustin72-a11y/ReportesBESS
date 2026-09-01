# BESS 5.18.20 — Tarifas CFE actualizables y sidebar limpia

## Resumen

Completa la persistencia de tarifas DIST/GDMTH/PDBT/T1 (APIs que faltaban desde
5.18.5) y elimina residuos de la guía/tooltips BESS en la barra lateral al
cambiar de módulo en la Suite.

## Cambios

- Constantes `ESQUEMA_PDBT` / `ESQUEMA_T1`, `ESQUEMAS_CALCULO` / `ESQUEMAS_CATALOGO`
- `archivo_tarifas_csv()` y lectura/escritura de catálogo con año
- CLI `--escribir-csv` / `--actualizar-bd` para presets PDBT y T1
- Admin de tarifas: selector DIST · GDMTH · PDBT · T1
- Import lazy de `bess.data.ingest.cfe` (Consultar Tarifa no falla al abrir)
- Limpieza compartida de sidebar (`bess/ui/sidebar_cleanup.py`) en Suite y hermanas
- Guía de visualizador BESS solo con títulos (sin resúmenes largos)

## Migración desde 5.18.19

```bash
cd ~/ReportesBESS
git fetch --tags
git checkout -f v5.18.20
docker compose up -d --build
```

Actualización manual de PDBT/T1 (opcional):

```bash
python3 scripts/consultar_tarifas_cfe.py --preset miguel_hidalgo --mes 8 --escribir-csv --actualizar-bd
python3 scripts/consultar_tarifas_cfe.py --preset tarifa1 --mes 8 --escribir-csv --actualizar-bd
```
