# BESS 5.18.31 — Suite IUSASOL

## Resumen

El periodo de las 23:05–23:55 y de las 00:00 se calculaba con el día
siguiente. En la noche del 15/09/2026 (martes, temporada 3) eso tomó el
16, que es festivo, y dejó **Base** donde corresponde **Intermedio**
(22:00–24:00). La marca en punto sigue cerrando la hora anterior, pero
ya no cambia de fecha. Hay que regenerar los reportes de septiembre:
el cron solo reescribe el último día y el CSV guardado conserva el
periodo anterior.

## Cambios

- `bess/cfe/periods.py`: las 23:05–00:00 son la hora 23 del día que cierra.
- `bess/cfe/periods_gdmth.py`: Aragón usa la misma marca.
- `analisis_perfil/marca_horaria.py`: la misma regla en Análisis de Perfil.
- `tests/test_periods.py`: festivo, sábado/domingo, cambio de temporada y año nuevo.
- Imagen Compose: `bess:5.18.31`.

## Migración desde 5.18.30

```bash
cd ~/ReportesBESS
git fetch --tags
git checkout -f v5.18.31
docker compose up -d --build
grep __version__ bess/__init__.py
```

Respalde `data/` como de costumbre antes de `git checkout -f`.
Después del despliegue, regenere los reportes del mes para corregir
el `PERIODO` ya escrito (el 15/09 y las noches de sábado y domingo).

## Pruebas

```bash
pytest tests/test_periods.py
```

## Versión anterior

- [5.18.30](RELEASE_NOTES_5.18.30.md)
