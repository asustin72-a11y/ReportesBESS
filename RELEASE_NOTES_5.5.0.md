# BESS 5.5.0

## Cambios principales

- **Pipeline solo por minuto:** diarios, acumulados y BESS se generan desde `COMBINADO_POR_MINUTO_*`. Ya no se crean `*_POR_HORA` ni `COMBINADO_POR_HORA`.
- **Día operativo:** ventana 00:05 → 00:00 del día siguiente. Columna `FECHA` en combinado; `FECHA_HORA` conserva el timestamp real del intervalo.
- **Neteo IUSA2:** `KWH_NETO = max(0, REC − ENT)` por intervalo de 5 min antes de agregar (alineado con detalle de energía).
- **IUSA1:** sin cambio de lógica (solo `KWH_REC`).
- **kVArh:** solo desde combinado minuto.
- **UI / PDF:** filtros y etiquetas por día operativo `(00:05 – 00:00)`.

## Migración

- Los CSV `*_POR_HORA*` en `data/ArchivosReporte/` de corridas anteriores pueden borrarse; el pipeline ya no los usa.
- Regenerar reportes: `python scripts/run_reporte_bess.py` o **Generar reportes** en la app.

## Versión anterior

- 5.4.0 — UI modular, sync ION + API, recibo CFE, PNG de gráficas.
