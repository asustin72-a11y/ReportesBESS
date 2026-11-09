# BESS 5.18.34 — Suite IUSASOL

## Resumen

Los selectores de fecha pueden recorrer el periodo **un día a la vez**.
El catálogo deja a **BESS Aragón** en la serie `CS4620 VL2E 19NB`, sin
cambiar el nombre del medidor.

## Cambios

- `bess/ui/components.py`: botones **◀ Ant.** y **Sig. ▶** en la fecha
  única y en Desde/Hasta. Un día suelto pasa al anterior o al siguiente.
  Un rango se desliza un día y conserva su longitud. En el extremo de los
  datos el botón queda deshabilitado.
- `bess/ui/pages.py`: resumen y tendencia usan ese control.
- `bess/ui/generacion_tab.py`: el mismo control en Generación.
- `data/Tarifas/Medidores.csv`: `BESS_ARAGON` pasa de `CS1991` a `CS4620`.
- `tests/test_recorrer_dia.py`.
- Imagen Compose: `bess:5.18.34`.

El catálogo en marcha vive en SQLite. Este CSV no reescribe
`catalog_medidores` si la base ya tiene filas. En el servidor la serie
`CS4620` ya está guardada en la base.

## Migración desde 5.18.33

```bash
cd ~/ReportesBESS
git fetch --tags
git checkout -f v5.18.34
docker compose up -d --build
grep __version__ bess/__init__.py
```

Respalde `data/` como de costumbre antes de `git checkout -f`.

## Pruebas

```bash
pytest tests/test_recorrer_dia.py
```

## Versión anterior

- [5.18.33](RELEASE_NOTES_5.18.33.md)
