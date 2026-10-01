# BESS 5.18.30 — Suite IUSASOL

## Resumen

El **Perfil de carga** del último día del mes se dibujaba mal: la base
ordena `FECHA_HORA` como texto (`dd/mm/aaaa`), así que `01/10 00:00` queda
antes que `30/09`. Plotly unía esos puntos y el área se veía como una banda
plana. La gráfica ahora se dibuja en orden cronológico. No cambia el cron,
los datos ni el cálculo de capacidad.

## Cambios

- `bess/charts/profile.py`: orden estable por `DATETIME` antes de armar las series.
- `tests/test_profile_yaxis_range.py`: día operativo 30/09 que incluye `01/10 00:00`.
- Imagen Compose: `bess:5.18.30`.

## Migración desde 5.18.29

```bash
cd ~/ReportesBESS
git fetch --tags
git checkout -f v5.18.30
docker compose up -d --build
grep __version__ bess/__init__.py
```

Respalde `data/` como de costumbre antes de `git checkout -f`.
Si `git fetch` falla por disco lleno, limpie imágenes Docker viejas y
vuelva a intentar.

## Pruebas

```bash
pytest tests/test_profile_yaxis_range.py
```

## Versión anterior

- [5.18.29](RELEASE_NOTES_5.18.29.md)
