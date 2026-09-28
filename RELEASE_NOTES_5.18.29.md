# BESS 5.18.29 — Suite IUSASOL

## Resumen

En **Análisis → Demanda** de IUSA 1 e IUSA 2 aparece la gráfica de
**demanda real de planta** (ION + generación + descarga BESS − recarga),
rolada 15 min. El expander arranca **cerrado**. No cambia Con/Sin BESS,
Capacidad CFE, Shapley, PDF ni sidebar.

## Cambios

- `bess/charts/profile.py`: serie y gráfica `Demanda real` (DIST).
- `bess/ui/pages.py`: expander en Análisis → Demanda.
- `tests/test_demanda_real_dist.py`.
- Imagen Compose: `bess:5.18.29`.

Aragón (GDMTH) no usa este expander: sigue con la demanda real del perfil.

## Migración desde 5.18.28

```bash
cd ~/ReportesBESS
git fetch --tags
git checkout -f v5.18.29
docker compose up -d --build
grep __version__ bess/__init__.py
```

Respalde `data/` como de costumbre antes de `git checkout -f`.
Si `git fetch` falla por disco lleno, limpie imágenes Docker viejas y
vuelva a intentar.

## Pruebas

```bash
pytest tests/test_demanda_real_dist.py tests/test_demanda_tabla_analisis.py
```

## Versión anterior

- [5.18.28](RELEASE_NOTES_5.18.28.md)
