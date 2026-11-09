# BESS 5.18.36 — Suite IUSASOL

## Resumen

El build de la imagen instala `libatomic1` antes de Playwright.
Sin esa librería, el Node del driver no arranca en `python:3.12-slim`
y `playwright install` termina con el código 127.

## Cambios

- `Dockerfile`: `apt-get install libatomic1` junto con `ca-certificates` y `curl`.
- Imagen Compose: `bess:5.18.36`.

## Migración desde 5.18.35

```bash
cd ~/ReportesBESS
git fetch --tags
git checkout -f v5.18.36
docker compose up -d --build
grep __version__ bess/__init__.py
```

Respalde `data/` como de costumbre antes de `git checkout -f`.

## Versión anterior

- [5.18.35](RELEASE_NOTES_5.18.35.md)
