# BESS 5.18.37 — Suite IUSASOL

## Resumen

**Sig. ▶** y **◀ Ant.** actualizan la fecha en el callback del botón,
antes de que Streamlit cree el selector. Antes, **Sig. ▶** escribía
la sesión cuando el `date_input` ya existía y la página mostraba
`StreamlitAPIException`.

## Cambios

- `bess/ui/components.py`: el desplazamiento del periodo va en `on_click`.
- Imagen Compose: `bess:5.18.37`.

## Migración desde 5.18.36

```bash
cd ~/ReportesBESS
git fetch --tags
git checkout -f v5.18.37
docker compose up -d --build
grep __version__ bess/__init__.py
```

Respalde `data/` como de costumbre antes de `git checkout -f`.

## Pruebas

```bash
pytest tests/test_recorrer_dia.py
```

## Versión anterior

- [5.18.36](RELEASE_NOTES_5.18.36.md)
