# BESS 5.18.32 — Suite IUSASOL

## Resumen

El perfil de carga abre en el último día con datos (el 01/10 ya no queda
oculto detrás de ayer) y, en un solo día, el eje muestra la fecha debajo
de la hora, así la medianoche de cierre no se lee como otro `00:00`.
En el catálogo, el superadmin descarga los CSV y PDF del servidor desde
la pestaña Reportes, sin WinSCP.

## Cambios

- `bess/ui/pages.py`: el rango del perfil arranca en el día operativo más reciente.
- `bess/charts/profile.py`: eje de un día con `%H:%M` y `dd/mm`.
- `bess/ui/catalog_admin/reportes_descarga.py`: listado y descarga de
  `ArchivosReporte` y PDF diarios. Solo CSV y PDF; rechaza rutas fuera de esas carpetas.
- `bess/ui/catalog_admin/page.py`: pestaña Reportes.
- Imagen Compose: `bess:5.18.32`.

## Migración desde 5.18.31

```bash
cd ~/ReportesBESS
git fetch --tags
git checkout -f v5.18.32
docker compose up -d --build
grep __version__ bess/__init__.py
```

Respalde `data/` como de costumbre antes de `git checkout -f`.
Una sesión de Streamlit ya abierta conserva las fechas que tenía
elegidas; una sesión nueva abre en el último día.

## Pruebas

```bash
pytest tests/test_profile_yaxis_range.py tests/test_catalog_descarga_reportes.py
```

## Versión anterior

- [5.18.31](RELEASE_NOTES_5.18.31.md)
