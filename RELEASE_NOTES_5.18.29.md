# BESS 5.18.29 — Suite IUSASOL

## Resumen

En **Análisis → Demanda** de IUSA 1 e IUSA 2 aparece la gráfica de
**demanda real de planta** (ION + generación + descarga BESS − recarga),
rolada 15 min. El expander arranca **cerrado**. No cambia Con/Sin BESS,
Capacidad CFE, Shapley, PDF ni sidebar.

También se incluye `scripts/limpiar_disco_servidor.sh` para liberar disco
en el host (Docker, respaldos, git gc) sin tocar `data/` ni volúmenes.

## Cambios

- `bess/charts/profile.py`: serie y gráfica `Demanda real` (DIST).
- `bess/ui/pages.py`: expander en Análisis → Demanda.
- `tests/test_demanda_real_dist.py`.
- `scripts/limpiar_disco_servidor.sh`.
- Imagen Compose: `bess:5.18.29`.

Aragón (GDMTH) no usa este expander: sigue con la demanda real del perfil.

## Migración desde 5.18.28

```bash
cd ~/ReportesBESS
# si git fetch falla por disco:
#   bash scripts/limpiar_disco_servidor.sh --dry-run
#   bash scripts/limpiar_disco_servidor.sh
git fetch --tags
git checkout -f v5.18.29
docker compose up -d --build
grep __version__ bess/__init__.py
```

Respalde `data/` como de costumbre antes de `git checkout -f`.

Si el script de limpieza aún no está en el servidor, cópielo antes del
fetch (el archivo es pequeño) o libere Docker a mano.

## Pruebas

```bash
pytest tests/test_demanda_real_dist.py tests/test_demanda_tabla_analisis.py
```

## Versión anterior

- [5.18.28](RELEASE_NOTES_5.18.28.md)
