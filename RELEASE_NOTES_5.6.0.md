# BESS 5.6.0

## Resumen

Modularización por catálogo CSV y subestación (`IUSA_1` / `IUSA_2`), migración de SQLite, validación de medidores, limpieza legacy y corrección de parseo de fechas en el pipeline.

## Cambios principales

### Catálogo y rutas (Fases 1–2)
- Catálogo en `data/Tarifas/` (`Subestaciones.csv`, `Medidores.csv`, `Tipo_Medidor.csv`) con validación al arranque.
- Rutas por subestación: `ArchivosFuente/{Sub}/`, `ArchivosProcesados/{Sub}/`, `ArchivosReporte/{Sub}/`, `ReportesDiarios/{Sub}/`.
- Lectura con fallback a CSV planos legacy en `ArchivosReporte/` y `ArchivosProcesados/` (solo lectura).

### Base de datos (Fase 3)
- `medidor_id` en SQLite alineado al `Nombre` del catálogo.
- Script `scripts/migrar_bd_perfiles.py` con respaldo automático.

### Pipeline (Fases 4–5)
- Consolidación BESS → `BESS_IUSA_1.csv` / `BESS_IUSA_2.csv`.
- Identificación, verificación y filtrado por subestación.
- Columna `Validado` en `Medidores.csv`; sync marca medidores tras export OK.
- Bloqueo de **Generar reportes** / **Procesar todo** si faltan medidores sin validar.

### Limpieza y regeneración (Fase 7)
- `scripts/limpiar_datos_legacy.py` (`--dry-run`, `--ejecutar`, `--corrida-completa`).
- `bess/data/pipeline/cleanup_legacy.py` y panel **Mantenimiento (Fase 7)** en sidebar admin.

### Correcciones
- Parseo unificado de fechas (`dd/mm/yyyy` con/sin segundos e ISO) en `bess/core/dates.py` y `bess/data/ingest/readers.py`.
- Filtrado ION ∩ BESS restaura intersección completa de timestamps (acumulados y recibo CFE cuadran con junio completo).
- `generar_diarios_con_demandas`: grupos sin demanda rodante ya no rompen el pipeline (`idxmax` con NA).
- Reporteador: `ruta_p` en lugar de `ruta` indefinida.

## Migración desde 5.5.0

1. Respaldar `data/bess_perfiles.db` y `data/Tarifas/`.
2. Ejecutar `python scripts/migrar_bd_perfiles.py` si aún usa IDs legacy en BD.
3. Opcional — regenerar todo con nomenclatura nueva:
   ```bash
   python scripts/limpiar_datos_legacy.py --ejecutar --corrida-completa
   ```
4. O flujo manual: **Sincronizar** → **Verificar** → **Filtrar** → **Generar reportes**.

## Scripts nuevos

| Script | Uso |
|--------|-----|
| `scripts/migrar_bd_perfiles.py` | Migrar `medidor_id` en SQLite |
| `scripts/limpiar_datos_legacy.py` | Limpieza CSV legacy + corrida opcional |

## Versión anterior

- **5.5.0** — Pipeline por minuto, día operativo 00:05–00:00, neteo IUSA2.
