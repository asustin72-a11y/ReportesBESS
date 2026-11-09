# BESS 5.18.35 — Suite IUSASOL

## Resumen

Si un medidor no está en la API, su error se anota y la descarga
**sigue con los demás**.

## Cambios

- `bess/data/ingest/iusasol/sync_db.py`: `sincronizar_api` ya no regresa
  al primer `IusasolError` o `ValueError`. El medidor queda en el resumen
  con su error y el ciclo continúa.
- `tests/test_sync_api_continua_sin_medidor.py`.
- Imagen Compose: `bess:5.18.35`.

## Migración desde 5.18.34

```bash
cd ~/ReportesBESS
git fetch --tags
git checkout -f v5.18.35
docker compose up -d --build
grep __version__ bess/__init__.py
```

Respalde `data/` como de costumbre antes de `git checkout -f`.

## Pruebas

```bash
pytest tests/test_sync_api_continua_sin_medidor.py
```

## Versión anterior

- [5.18.34](RELEASE_NOTES_5.18.34.md)
