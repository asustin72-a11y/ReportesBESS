# BESS 5.18.28 — Suite IUSASOL

## Resumen

Release **completo** sobre `5.18.25`: los cinco módulos del selector
(BESS, Granja Solar, Descargas API, Análisis de Perfil, Consultar Tarifa)
y, en **Análisis → Demanda**, máximos por periodo con **demanda rolada
15 min** hasta la fecha de corte.

**No** use `v5.18.26` ni `v5.18.27` en el servidor: esos tags salieron de
una rama antigua de tres módulos y ocultan Análisis de Perfil y Consultar
Tarifa.

## Cambios (desde 5.18.25)

- `bess/cfe/report_data.py`: máximos Base / Intermedio / Punta sobre
  `*_kW_DEM_15min` del combinado, con máscara TOU (se ignoran los dos
  primeros intervalos de cada racha tarifaria) y ceil CFE.
- `bess/ui/pages.py`: tabla y textos de Análisis → Demanda; si faltan
  columnas del combinado, el respaldo lee la fila de `ACUMULADOS` de la
  fecha de corte (ya no `idxmax` del mes).
- `tests/test_demanda_tabla_analisis.py`.
- Imagen Compose: `bess:5.18.28`.

El catálogo de planta (varios tipo 5 en IUSA 1; granja tipo 4 + FV tipo 5
en IUSA 2) ya era válido en `5.18.25`. No hay que borrar medidores ni
regenerar combinados.

## Migración desde 5.18.25 (o desde 5.18.26/27 incompletos)

```bash
cd ~/ReportesBESS
git fetch --tags
git checkout -f v5.18.28
docker compose up -d --build
grep __version__ bess/__init__.py
```

Respalde `data/` como de costumbre antes de `git checkout -f`.

Si el selector muestra solo tres tarjetas, está en `v5.18.26`/`v5.18.27`.
Pase a `v5.18.28`.

## Pruebas

```bash
pytest tests/test_demanda_tabla_analisis.py tests/test_demand_periodo.py
```

## Versión anterior

- [5.18.25](RELEASE_NOTES_5.18.25.md)
