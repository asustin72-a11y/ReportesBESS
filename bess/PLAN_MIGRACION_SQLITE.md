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

### Fase 4 — Filtrar sin relectura completa · Hecho (esta sesión)

`bess/data/pipeline/filter.py` seguía calculando la intersección de fechas
completa en cada corrida (eso no cambia: BESS y cada medidor de consumo
siguen leyéndose completos desde `ArchivosProcesados/*.csv`, porque esa
lectura ya es un requisito para calcular bien la intersección), pero antes
reescribía cada `*_Filtrado.csv` completo sin importar cuánto de ese
resultado ya estaba escrito de una corrida anterior.

Se agregó `_escribir_filtrado()`: recibe el conjunto de fechas aceptadas
(la intersección, sin cambios en su cálculo) y decide si puede *anexar*
solo el tramo nuevo (cursor sobre la última Fecha ya escrita en el destino,
usando los mismos helpers de `clean.py` de Fase 3) o si tiene que
recalcular y reescribir completo (primera vez, o cambio de formato de
columnas). Es seguro anexar solo lo nuevo porque Verificar garantiza que
cada CSV procesado no tiene huecos internos dentro de su propio rango: la
intersección de dos rangos sin huecos es a su vez un rango sin huecos, así
que una fecha nunca queda "saltada" por quedar por debajo del cursor sin
haber sido nunca escrita. Se aplica a los cuatro archivos que genera cada
subestación: el filtrado de cada medidor de consumo, `BESS_*_Filtrado.csv`,
y (cuando aplican) Granja y Cogeneración.

Validado con 6 pruebas de equivalencia (`tests/test_filter_incremental.py`:
primera corrida completa, incremental multi-corrida == completo -- con
datos sintéticos y también con datos reales de IUSA_1 (ION ∩ BESS) --,
no-op sin novedades, fallback a completo si cambia el formato de columnas,
y que la transformación de intercambio REC/ENT de Banco 1 solo se aplique
al tramo nuevo) más una prueba de integración que corre
`_filtrar_datos_impl()` dos veces seguidas contra los datos reales del
repo (las tres subestaciones) y confirma que la segunda corrida no cambia
ni un byte de los `*_Filtrado.csv` ya escritos. Suite completa: 86 pruebas.

Sigue pendiente (no es parte de esta fase, ver Fase 5+): mover la *lectura*
de BESS/medidores de consumo a consultas directas sobre SQLite en vez de
`ArchivosProcesados/*.csv` completos -- eso es un cambio más grande que
"hacer incremental el CSV" y se deja para cuando se ataque esa capa.

### Fase 5 — Combinados, diarios y acumulados desde BD

**Qué cambia:** `bess/data/aggregates/{combined,daily,accumulated,granja,
bess_daily,generacion}.py` (~800 líneas en total) generan
`COMBINADO_POR_MINUTO_*.csv`, `ENERGIA_*_POR_DIA.csv` y `ACUMULADOS_*.csv` —
la capa que sí calcula demanda rodante, periodos CFE y kWh netos, no solo
copia datos. Son candidatos a convertirse en tablas materializadas en
SQLite, recalculadas solo para el rango de fechas afectado por el último
sync; por ahora esta fase se está dividiendo en sub-pasos por archivo
(según lo previsto), empezando por `combined.py`.

**Riesgo:** medio-alto. Es la lógica de cálculo, no solo de transporte de
datos — cualquier diferencia de redondeo o de agrupación aquí sí cambia un
número que ve el cliente.

#### Fase 5.1 — combined.py incremental · Hecho (esta sesión)

`generar_combinado_por_minuto()` combinaba BESS + medidor de consumo
(merge por `FECHA_HORA`, sigue siendo completo: ya requiere leer
`ArchivosProcesados/*_Filtrado.csv` enteros) y luego calculaba columnas
derivadas -- HORA, PERIODO CFE, kW, kWh netos, mejora BESS y demanda
rodante de 15 min con reinicio mensual -- sobre **todo** el histórico en
cada corrida, reescribiendo `COMBINADO_POR_MINUTO_*.csv` completo.

Ahora, si el destino ya existe con cursor legible (última `FECHA_HORA`
escrita) y columnas compatibles, esas columnas derivadas solo se calculan
para las filas nuevas y se anexan (no se recalcula ni se reescribe el
histórico ya escrito). El caso delicado es la demanda rodante: es un
rolling de 3 filas (15 min / 5 min) reiniciado al inicio de cada mes
operativo, así que para que la primera fila nueva dé el mismo resultado
que una corrida completa hace falta incluir como contexto las 2 filas
previas al corte -- si esas 2 filas de contexto caen en un mes distinto al
de las filas nuevas, `groupby(mes).rolling()` las separa solas y el
reinicio mensual sigue funcionando igual que antes.

`procesar_grupo()` (el orquestador que encadena combinado → diario →
acumulados) trataba `len(df_combinado) == 0` como fallo del paso; con la
versión incremental, "sin filas nuevas" ya no es un DataFrame vacío (se
devuelve el merge completo, sin las columnas derivadas del histórico ya
escrito) para no confundir un no-op con un error real.

Validado con 7 pruebas (`tests/test_combined_incremental.py`): primera
corrida completa, incremental multi-corrida == completo con un split a
mitad de mes y con un split justo en la frontera de un mes (ejercitando el
reinicio de la demanda rodante), no-op sin filas nuevas (y que no se
reporte como fallo), fallback a completo si cambia el formato de columnas,
equivalencia con datos reales de IUSA_1 (ION ∩ BESS), y una corrida real de
`procesar_grupo()` dos veces seguidas contra los datos reales del repo.
Suite completa: 93 pruebas.

Pendiente dentro de esta misma fase: `daily.py`, `accumulated.py`,
`bess_daily.py`, `granja.py` y `generacion.py` siguen releyendo el
combinado completo y reescribiendo sus salidas completas en cada corrida
(no rompen con lo anterior -- releen el CSV ya actualizado del disco --
pero no se benefician todavía de la incrementalidad).

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