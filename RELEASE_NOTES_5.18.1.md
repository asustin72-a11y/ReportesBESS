# BESS 5.18.1 — Suite IUSASOL

## Resumen

**Descargas API** deja de vivir dentro del sidebar/barra de BESS y pasa a ser
el **tercer módulo** del selector post-login, junto a BESS y Granja Solar.

## Cambios

- Selector Suite: **BESS | Granja Solar | Descargas API** (todos los roles).
- Módulo Descargas con **Volver a la Suite** / **Cerrar sesión** en barra superior.
- Eliminado expander Descargas del sidebar de BESS y el botón Descargas de la
  barra del reporteador BESS.
- Imagen Compose: `bess:5.18.1`.

## Migración desde 5.18.0

```bash
cd ~/ReportesBESS
git fetch --tags
git checkout -f v5.18.1
docker compose up -d --build
grep __version__ bess/__init__.py
```

Tras el login debe verse la tarjeta **Descargas API** al lado de BESS y Granja.

## Versión anterior

- [5.18.0](RELEASE_NOTES_5.18.0.md)
