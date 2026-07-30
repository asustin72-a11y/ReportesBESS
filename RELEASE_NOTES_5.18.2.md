# BESS 5.18.2 — Suite IUSASOL

## Resumen

Corrige el título del módulo **Descargas API**: ya no se muestra HTML crudo
con estilos inline; usa el header de la Suite / captions nativos de Streamlit.

## Cambios

- `descargas/ui/pages.py`: título sin `<div style=…>`; header standalone alineado
  a clases `app-header` de BESS/Granja.
- Imagen Compose: `bess:5.18.2`.

## Migración desde 5.18.1

```bash
cd ~/ReportesBESS
git fetch --tags
git checkout -f v5.18.2
docker compose up -d --build
grep __version__ bess/__init__.py
```

## Versión anterior

- [5.18.1](RELEASE_NOTES_5.18.1.md)
