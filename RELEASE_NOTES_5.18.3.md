# BESS 5.18.3 — Suite IUSASOL

## Resumen

Corrige los picos a **0 kW** en la gráfica de demanda del día tras el
aislamiento TOU: la demanda rolada 15 min vuelve a ser **continua por mes**
(apta para curvas), y el aislamiento de periodos se aplica solo al **detectar
máximos** (máscara que excluye los 2 primeros intervalos de cada racha de
`PERIODO`).

## Cambios

- `bess/core/demand.py`: rolling publicado con `demanda_rodante_15min_por_mes`;
  nueva `mascara_valida_para_maximo` / `aplicar_mascara_demanda_maximo`.
- `bess/data/aggregates/combined.py`: columnas `*_DEM_15min` continuas por mes.
- `bess/data/aggregates/daily.py`: `idxmax` de demandas máximas con máscara TOU.
- `bess/cfe/shapley.py`: misma lógica (rolling continuo + máscara en punta).
- Tests de demanda y combinado incremental actualizados.
- Imagen Compose: `bess:5.18.3`.

## Migración desde 5.18.2

```bash
cd ~/ReportesBESS
git fetch --tags
git checkout -f v5.18.3
docker compose up -d --build
grep __version__ bess/__init__.py
```

**Importante:** regenerar COMBINADO / diarios (Verificar → Filtrar → Generar,
o el ciclo de sync del cron) para que las columnas `*_DEM_15min` dejen de
traer ceros artificiales en cambios de periodo.

## Versión anterior

- [5.18.2](RELEASE_NOTES_5.18.2.md)
