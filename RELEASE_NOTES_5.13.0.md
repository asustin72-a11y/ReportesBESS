# BESS 5.13.0

## Resumen

Confiabilidad de datos: cuatro bugs reales de producción corregidos (degradación a cero en syncs en vivo, truncado por escritura no atómica, cursor de generación congelado por ceros de relleno futuro, y relleno de ceros por adelantado de la API que contaminaba `sync_state`), aviso en la app cuando el reporte está desactualizado respecto al último sync, y un primer paso de rediseño visual (UI plana). Suite de pruebas ampliada.

## Cambios principales

### Protección de datos en syncs en vivo

- **`no_degradar_a_ceros`** en sync API/Modbus (`iusasol/sync_db.py`, `granja/sync_db.py`, `ion/sync.py`): un lote entero en cero por falla transitoria ya no pisa lecturas reales previas.
  → `tests/test_db_upsert_no_degradar_a_ceros.py`

### Escritura atómica en el pipeline

- **`bess/core/atomic_io.py`**: escribe a temporal y solo reemplaza el archivo final si la escritura termina bien. Aplicado a los escritores del pipeline (verify, clean, combined, granja, bess_daily, accumulated, daily, export_csv).
  → `tests/test_atomic_io.py`

### Aviso de reporte desactualizado

- Compara `sync_state` (SQLite) vs última fecha del combinado CSV; aviso si el desfase supera 3 horas.
- Cubre consumo (facturación) y generación por subestación.
  → `tests/test_pipeline_status_desfase.py`

### Reportes de generación: cursor incremental

- `granja.py` reescribe ventana de días recientes (como `combined.py`) en vez de solo anexar tras el cursor — evita ceros de relleno futuro “congelados”.
  → `tests/test_granja_relleno_ceros.py`

### Eliminación del relleno de ceros por adelantado

- Al sincronizar el día en curso, se descartan slots futuros antes de guardar en SQLite (`_recortar_slots_futuros` / `_recortar_registros_futuros`).
- Script opcional: `scripts/limpiar_relleno_futuro.py` para purgar ceros futuros ya escritos.
  → `tests/test_recorte_relleno_futuro.py`

### Gráficas y UI

- Eje Y dinámico en tendencias y perfil de carga (IUSA_ARAGON ya no queda aplastado).
- Estilos: aplanar tarjetas/nav/callouts (sin sombras ni degradados decorativos).

### Pipeline incremental (Fases 1–6, base de esta línea)

Verify / export / consolidate / filter / aggregates con cursor o ventana; no requiere regenerar todo el histórico al desplegar.

## Archivos nuevos

- `bess/core/atomic_io.py`
- `scripts/limpiar_relleno_futuro.py`
- `tests/test_db_upsert_no_degradar_a_ceros.py`
- `tests/test_atomic_io.py`
- `tests/test_trends_yaxis_range.py`
- `tests/test_profile_yaxis_range.py`
- `tests/test_pipeline_status_desfase.py`
- `tests/test_granja_relleno_ceros.py`
- `tests/test_recorte_relleno_futuro.py`

## Migración desde 5.12.0

```bash
cd ~/ReportesBESS
git fetch --tags
git checkout -f v5.13.0
docker compose up -d --build
```

**No hace falta regenerar todos los reportes.** El pipeline sigue incremental y compatible con CSV existentes. Tras el deploy, un ciclo de sync + procesar (o el cron) pone al día la ventana abierta.

Opcional si hubo contaminación por ceros futuros en generación: un Reportes de ese sitio, o `python scripts/limpiar_relleno_futuro.py`.

**Pendiente (no incluido):** migración CSV → SQLite como fuente de verdad del reportador (pausada a propósito para evaluar 5.13.0 en servidor primero).

## Versión anterior

- **5.12.0** — Sección Emisiones CO₂ Scope 2 con PDF descargable.
