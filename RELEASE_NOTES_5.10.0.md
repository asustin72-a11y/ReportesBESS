# BESS 5.10.0

## Resumen

Soporte **GDMTH** para **IUSA_ARAGON**: horarios de periodo, tarifas MEM por esquema, cargo de **Distribución** separado de **Capacidad**, recibo simulado GDMTH y catálogo de datos del cliente para el layout del recibo.

IUSA_1 e IUSA_2 siguen en esquema **DIST** sin cambios de lógica de capacidad.

## Cambios principales

### Esquema tarifario por subestación
- `esquema_tarifa_id` en catálogo: **DIST** (IUSA_1, IUSA_2) · **GDMTH** (IUSA_ARAGON).
- Factor CFE para DemandaCalculadaCFE: **0.74** (DIST) · **0.57** (GDMTH).
- `cargar_tarifas(esquema)` en energía, arbitraje, capacidad, Shapley, recibo y PDF diario.

### Horarios GDMTH
- `bess/cfe/periods_gdmth.py` y `periodo_por_fecha_hora(..., esquema)` en el pipeline de agregados.
- Periodos horarios GDMTH aplicados a combinados, diarios, BESS diario y granja cuando la subestación es GDMTH.

### Tarifas GDMTH
- Fuente: `data/Tarifas/Tarifas GDMTH.txt` → `data/Tarifas/Tarifas_GDMTH_2026.csv`.
- `catalog_tarifas` con clave `(esquema_id, tarifa, mes)`; admin de tarifas con selector DIST / GDMTH.
- Tarifas GDMTH cargadas ene–jul 2026 (ago–dic en 0 hasta publicación).

### Capacidad y distribución GDMTH
- **Capacidad:** min(demanda punta rodada, DemandaCalculadaCFE) × tarifa Capacidad.
- **Distribución:** min(demanda máxima en cualquier horario, D_calc) × tarifa Distribución (`bess/cfe/distribution.py`).

### Recibo simulado GDMTH
- Layout MEM con líneas Suministro, Distribución, Capacidad y generación por periodo.
- Desglose: Cargo fijo + Energía + Cargo FP (sin línea Capacidad en pie; va en MEM).
- Datos del receptor desde `catalog_cliente_recibo` (pestaña **Cliente recibo** en Configuración).
- Fix HTML: filas de desglose sin indentación que Streamlit mostraba como texto.

### Datos y reportes Aragón
- Reportes procesados y acumulados de IUSA_ARAGON actualizados en `data/ArchivosProcesados/` y `data/ArchivosReporte/`.

## Migración desde 5.9.0

```bash
cd ~/ReportesBESS
git fetch --tags
git checkout -f v5.10.0
docker compose up -d --build
```

Tras actualizar, **regenerar reportes** si los CSV de Aragón no tienen columnas GDMTH o datos de cliente recibo:

```bash
python scripts/sincronizar_perfiles.py --quiet --procesar
```

En **Configuración → Cliente recibo** (superadmin), verifica los datos de IUSA_ARAGON antes de generar el PDF del recibo.

## Archivos nuevos

- `bess/config/esquema_tarifa.py`
- `bess/cfe/periods_gdmth.py`
- `bess/cfe/distribution.py`
- `bess/cfe/receipt/cliente.py`
- `bess/data/cliente_recibo_db.py`
- `bess/ui/catalog_admin/cliente_store.py`
- `data/Tarifas/Tarifas_GDMTH_2026.csv`

## Versión anterior

- **5.9.0** — Navegación por secciones, catálogo canónico y gráficas unificadas.
