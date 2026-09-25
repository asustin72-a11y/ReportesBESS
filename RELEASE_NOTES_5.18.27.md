# BESS 5.18.27 — Suite IUSASOL

## Resumen

El arranque ya no rechaza el catálogo real de planta: **varios medidores
tipo 5** (cogen + FV de azotea) y **granja tipo 4 con FV tipo 5** en la
misma subestación.

Eso corrige el bloqueo *Configuración de medidores inválida* en IUSA 1
(Generacion=2 con más de un tipo 5) e IUSA 2 (Generacion=1 con tipo 5).

## Cambios

- `bess/config/catalog.py`: `Generacion=2` exige al menos un tipo 5 (sin
  tope de uno); `Generacion=1` sigue exigiendo tipo 4 con grupo y **admite**
  tipo 5 opcional.
- Textos en Administrar catálogo (`catalog_admin/page.py`, `service.py`).
- `tests/test_catalog_generacion.py`.
- Imagen Compose: `bess:5.18.27`.

No hay que borrar medidores ni regenerar CSV. Recargar la aplicación
después del deploy.

## Migración desde 5.18.26

```bash
cd ~/ReportesBESS
git fetch --tags
git checkout -f v5.18.27
docker compose up -d --build
grep __version__ bess/__init__.py
```

Respalde `data/` como de costumbre antes de `git checkout -f`.

## Pruebas

```bash
pytest tests/test_catalog_generacion.py
```

## Versión anterior

- [5.18.26](RELEASE_NOTES_5.18.26.md)
