# Plan — reducir la dependencia de CSV (migración a SQLite)

Documento de referencia para la segunda migración del proyecto: de "hoja de
Excel con pasos encadenados" (Sincronizar → Verificar → Filtrar → Reportes,
cada uno leyendo y reescribiendo CSV completos) a un pipeline que usa la base
de datos como fuente de verdad en cada etapa, no solo en la ingesta.

Ver [`ARCHITECTURE.md`](ARCHITECTURE.md) para la migración de monolito a
paquete modular (`bess/*`), ya completada — este documento es un eje distinto:
dónde vive el dato, no cómo está organizado el código.

## Por qué

La app nació como hoja de Excel y todavía se comporta como una: cada paso del
pipeline relee un CSV completo, lo transforma y reescribe el CSV completo
para que el siguiente paso haga lo mismo. Con meses de histórico esto es
lento (se demostró en Fase 1: 70 días × relectura completa = trabajo
cuadrático) y frágil (un CSV a medio escribir, abierto en Excel, o con
formato inconsistente rompe todo lo que viene después). Ya existe una base de
datos (`data/bess_perfiles.db`) que resuelve esto para la ingesta; el resto
del pipeline no la usa todavía.

## Estado actual

```
Ingesta (ION Modbus, API IUSASOL, API Granja)
        │
        ▼
   SQLite: perfil_carga, sync_state, sync_log, catálogo   [BD — Hecho]
        │
        ▼  export_csv.py (exporta histórico COMPLETO cada sync)
   ArchivosFuente/*.csv                                    [CSV]
        │
        ▼  Verificar (verify.py) — incremental desde Fase 1 de esta sesión
   ArchivosProcesados/*.csv                                [CSV]
        │
        ▼  Filtrar (filter.py) — intersección de fechas, reescribe completo
   ArchivosProcesados/*_Filtrado.csv                        [CSV]
        │
        ▼  aggregates/{combined,daily,accumulated,granja,bess_daily}.py
   ArchivosReporte/COMBINADO_*, ENERGIA_*_POR_DIA, ACUMULADOS_*  [CSV]
        │
        ▼
   reports/*_pdf.py  +  ui/{pages,reportes_tab,generacion_tab,...}.py
```

Todo lo que está debajo de la primera línea de SQLite sigue siendo CSV de
punta a punta. Verificar ya dejó de reprocesar el histórico completo en cada
corrida (cursor incremental); todo lo demás en la cadena todavía lo hace.

## Principio de trabajo (el que ya se siguió en Verificar)

Un cambio a la vez, cada uno con: prueba de equivalencia (resultado nuevo ==
resultado viejo, no solo "no truena"), validación contra una copia aislada de
datos reales del repo, y commit propio. Los números que produce este sistema
son facturación real — no vale la pena ganar velocidad a cambio de arriesgar
un cálculo mal hecho que nadie note a tiempo.

## Fases

### Fase 0 — Ingesta a SQLite · Hecho

`bess/data/ingest/{ion,iusasol,granja}/sync_db.py` escriben directo a
`perfil_carga` (con `UNIQUE(medidor_id, fecha)` y cursor por medidor en
`sync_state`). El catálogo de medidores/subestaciones/tarifas también vive en
SQLite. Esto ya existía antes de esta sesión.

### Fase 1 — Verificar incremental · Hecho (esta sesión)

`bess/data/pipeline/verify.py`: cursor sobre el CSV ya procesado, solo
verifica (dedup + huecos) las filas nuevas y las anexa. Ver commits
`c3ba48a` y `1774799`.

### Fase 2 — Exportar incremental · Hecho (esta sesión)

`bess/data/ingest/ion/export_csv.py`: cursor sobre el CSV ya exportado
(última `Fecha` escrita); en cada sincronización, si no se piden `desde`/
`hasta` explícitos, solo se consultan a `perfil_carga` las filas
posteriores al cursor y se anexan, en vez de reexportar el histórico
completo. Un `desde`/`hasta` explícito (re-export puntual, p.ej. para
reparar datos) sigue sobrescribiendo el archivo completo, sin cambios.
Incluye el caso de medidores API/Granja con relleno de medianoche
(`gaps.py`): el contexto previo al cursor (`contexto_previo_bd`) se pasa
igual que antes se pasaba solo cuando había un `desde` explícito, para que
el relleno de 00:00 siga detectando el salto 23:55→00:05 aunque el corte
de la exportación caiga a media tabla.

Validado con 6 pruebas de equivalencia (`tests/test_export_csv_incremental.py`,
medidor ION y medidor API/Granja con medianoche) y contra una copia de la
base de datos real (dos medidores, export incremental multi-corrida ==
export completo, exacto).

**Hallazgo posterior:** el cron de 15 min corre `sincronizar_perfiles.py
--procesar`, que encadena Exportar -> Verificar -> Filtrar -> Reportes en
una sola corrida. `filter.py` borraba `ArchivosFuente` al final de cada
Filtrar exitoso -- el mismo archivo que Fase 2 usa como cursor. Con eso,
el cursor nunca sobrevivía al siguiente ciclo: cada corrida del cron caía
de vuelta a exportación completa, dejando a Fase 2 correcta pero inerte
en producción. Se quitó esa limpieza automática (`limpiar_archivos_fuente()`
sigue disponible para uso manual); ver `tests/test_filter_conserva_fuente.py`.
Suite completa: 75 pruebas.

### Fase 3 — Consolidado BESS incremental · Hecho (esta sesión)

`bess/data/pipeline/bess_consolidate.py`: cursor sobre `BESS_{sub}.csv`
(vía los nuevos helpers compartidos en `clean.py`: `cursor_archivo_limpio`,
`columnas_archivo_limpio`, `anexar_archivo_limpio`). Si ya existe un
consolidado con cursor legible y columnas compatibles, solo se suman y
anexan las filas nuevas de cada medidor BESS; la primera vez (o si cambia
el formato) recalcula completo, igual que antes.

Bug encontrado y corregido de paso: `cursor_archivo_limpio` parseaba la
Fecha sin `dayfirst=True`, pero `normalizar_fecha()` escribe DD/MM/YYYY
-- ambiguo para pandas cuando el día es ≤ 12 (p.ej. `01/02/2026`).

Validado con 4 pruebas (`tests/test_bess_consolidate_incremental.py`,
incluye la suma por outer-join como función pura) y contra el medidor
BESS real de IUSA_1 (5 sincronizaciones incrementales == una corrida
completa, exacto). Suite completa: 79 pruebas.

### Fase 4 — Filtrar sin relectura completa

**Qué cambia:** `bess/data/pipeline/filter.py` (~230 líneas) relee
`ArchivosProcesados/*.csv` completos, calcula la intersección de fechas
entre BESS y cada medidor de consumo (para que los reportes no comparen
periodos distintos) y reescribe `*_Filtrado.csv` completo (ya no borra
`ArchivosFuente` al final -- ver nota en Fase 2). Es candidato a moverse
a consultas directas sobre
SQLite (o sobre las tablas/vistas que resulten de Fases 2-3) en vez de leer
CSV — ya no solo "hacer incremental el CSV" sino empezar a no depender de él.

**Riesgo:** medio. La intersección de fechas es la lógica que garantiza que
BESS y el medidor de consumo se comparen en el mismo rango — un error aquí
se propaga a todos los reportes de esa subestación. El propio código ya trae
la advertencia ("Ejecute Verificar antes de Filtrar") como pista de que el
orden y la consistencia entre pasos importa.

**Nota aparte:** la limpieza de `ArchivosFuente` al final de este paso deja
de tener sentido en cuanto Fase 2 vuelva ese CSV innecesario — hay que
revisar esa función (`limpiar_archivos_fuente`) cuando se llegue aquí.

### Fase 5 — Combinados, diarios y acumulados desde BD

**Qué cambia:** `bess/data/aggregates/{combined,daily,accumulated,granja,
bess_daily,generacion}.py` (~800 líneas en total) generan
`COMBINADO_POR_MINUTO_*.csv`, `ENERGIA_*_POR_DIA.csv` y `ACUMULADOS_*.csv` —
la capa que sí calcula demanda rodante, periodos CFE y kWh netos, no solo
copia datos. Hoy cada uno relee CSV filtrado y reescribe completo. Son
candidatos a convertirse en tablas materializadas en SQLite, recalculadas
solo para el rango de fechas afectado por el último sync.

**Riesgo:** medio-alto. Es la lógica de cálculo, no solo de transporte de
datos — cualquier diferencia de redondeo o de agrupación aquí sí cambia un
número que ve el cliente. Conviene dividir esta fase en sub-pasos por
archivo (empezar por `combined.py`, que es la base de los otros tres) en vez
de intentarlo de una vez.

### Fase 6 — Reportes y UI apuntando a BD

**Qué cambia:** `bess/reports/{daily_pdf,accumulated_pdf,emisiones_pdf,
dia_tipo}.py`, `bess/charts/profile.py` y `bess/ui/{pages,generacion_tab,
pipeline_status,reportes_tab,sidebar}.py` leen `ArchivosReporte/*.csv`
directamente. Repuntarlos a consultas SQL (o a las tablas materializadas de
Fase 5) cierra la cadena.

**Riesgo:** alto en superficie (son ~9 archivos, varios en la capa que ve el
usuario en vivo), aunque cada cambio individual sea mecánico. Es la fase con
más probabilidad de que un error se note primero en pantalla que en una
prueba — dejarla para el final, con cada archivo probado por separado.

### Fase 7 — Decisión: ¿se retira el CSV?

No es código, es una decisión de producto que conviene tomar cuando se
llegue aquí, no ahora: si los CSV se eliminan del todo, o si se mantienen
como export de solo lectura / respaldo / algo que un admin pueda abrir en
Excel bajo demanda, pero fuera del camino crítico de escritura. Ambas son
razonables; depende de si alguien además de la app usa esos archivos hoy.

## Qué NO cambia en ninguna fase

- El esquema de columnas de los CSV que sí se mantengan (compatibilidad con
  Excel/exportes manuales).
- Los cálculos de periodos CFE, tarifas y arbitraje (`bess/cfe/`) — esta
  migración es de dónde vive el dato, no de cómo se calcula sobre él.
- El lock 