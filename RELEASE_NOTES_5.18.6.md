# BESS 5.18.6 — Suite IUSASOL

## Resumen

En **Análisis → Demanda**, el resumen de máximos por periodo muestra
**demanda rolada 15 min** (no kW instantáneo de 5 min) y corta en la
**fecha de corte**, no en el último día del mes en `ACUMULADOS`.

## Cambios

- `bess/cfe/report_data.py`: máximos por Base / Intermedio / Punta sobre
  `*_kW_DEM_15min` del combinado, con máscara TOU (se ignoran los dos
  primeros intervalos de cada racha tarifaria) y ceil CFE.
- `bess/ui/pages.py`: tabla y textos de Análisis → Demanda; si faltan
  columnas del combinado, el respaldo lee la fila de `ACUMULADOS` de la
  fecha de corte (ya no `idxmax` del mes).
- `tests/test_demanda_tabla_analisis.py`.
- Imagen Compose: `bess:5.18.6`.

No hay que regenerar combinados: las columnas de 15 min ya existen.

## Migración desde 5.18.5

```bash
cd ~/ReportesBESS
git fetch --tags
git checkout -f v5.18.6
docker compose up -d --build
grep __version__ bess/__init__.py
```

No requiere cambios de sudoers ni respaldo extra de `data/` más allá del
procedimiento habitual antes de `git checkout -f`.

## Pruebas

```bash
pytest tests/test_demanda_tabla_analisis.py tests/test_demand_periodo.py
```

## Versión anterior

- [5.18.5](RELEASE_NOTES_5.18.5.md)
