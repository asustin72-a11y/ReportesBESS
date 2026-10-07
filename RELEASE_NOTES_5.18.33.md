# BESS 5.18.33 — Suite IUSASOL

## Resumen

La **demanda real** de IUSA 2 (Análisis → Demanda → Demanda real de planta)
usa la planta completa, con el ION en el sentido de la carga:

**kWh = KWH_REC − KWH_ENT + generación + FV BESS Sur + FV CDPT + descarga BESS − carga BESS**

**kW = kWh × 12**, media de 15 minutos. Lo recibido por el ION suma y lo
entregado a la red resta. IUSA 1 no cambia. La serie sigue siendo solo
visual: no entra a Capacidad CFE ni a Shapley.

## Cambios

- `bess/charts/profile.py`: fórmula de IUSA 2 y lectura de
  `Generacion_IUSA_2`, `FV BESS Sur` y `FV CDPT`.
- `bess/ui/pages.py`: texto del expander.
- `tests/test_demanda_real_dist.py`.
- Imagen Compose: `bess:5.18.33`.

## Migración desde 5.18.32

```bash
cd ~/ReportesBESS
git fetch --tags
git checkout -f v5.18.33
docker compose up -d --build
grep __version__ bess/__init__.py
```

Respalde `data/` como de costumbre antes de `git checkout -f`.

## Pruebas

```bash
pytest tests/test_demanda_real_dist.py
```

## Versión anterior

- [5.18.32](RELEASE_NOTES_5.18.32.md)
