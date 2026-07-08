# BESS 5.11.0

## Resumen

Netmetering **GDMTH** para energía facturable, factor de potencia con **kVArh Q1+Q4** en GDMTH, perfil de **demanda real** en Aragón, filas REC/ENT en tablas y PDF diario, y sync API con fin de rango en **el día actual** (no mañana).

IUSA_1 e IUSA_2 (DIST) sin cambio de reglas de netmetering.

## Cambios principales

### Netmetering GDMTH (energía)
- Propiedad del esquema tarifario (`usa_netmetering()`).
- Consumo por periodo: **Σ REC − Σ ENT** (puede ser negativo por periodo).
- Demanda CFE: sin cambio (`max(0, REC−ENT)` por intervalo → rodante 15 min).
- Lectura centralizada en `bess/core/energia_periodo.py`.
- CSV diarios conservan REC/ENT brutos; consumo se calcula al leer.

### Factor de potencia (GDMTH / Aragón)
- kVArh mensual: **KVARH_Q1 + KVARH_Q4** (esquema GDMTH).
- Afecta recibo simulado, cargo FP y columnas `KVARH` / `KVARH_ACUM` tras reprocesar.

### UI y reportes
- Tabla **Detalle de Energía**: filas Recibida / Entregada del periodo (netmetering).
- PDF diario: mismas filas REC/ENT.
- Perfil de carga GDMTH: curva **Demanda real** (REC−ENT+gen+descarga−carga) con sombreado.

### Sync API ISOL
- `endDate` por defecto: **hoy** (`America/Mexico_City`), antes hoy+1.
- Solapamiento de 1 día en incremental sin cambio.

## Migración desde 5.10.0

```bash
cd ~/ReportesBESS
git fetch --tags
git checkout -f v5.11.0
docker compose up -d --build
```

Tras actualizar, **reprocesar** para regenerar energía, kVArh y acumulados (especialmente IUSA_ARAGON):

```bash
python scripts/sincronizar_perfiles.py --quiet --procesar
```

Si el catálogo en SQLite quedó desactualizado respecto a `data/Tarifas/*.csv`, reimporte desde **Configuración → Catálogo** o reinicie con BD de catálogo sincronizada.

## Archivos nuevos

- `bess/core/energia_periodo.py`

## Versión anterior

- **5.10.0** — GDMTH Aragón, recibo simulado y tarifas por esquema.
