# BESS 5.13.0 (borrador)

## Resumen

Sesión centrada en confiabilidad de datos: tres bugs reales de producción corregidos (degradación a cero en syncs en vivo, truncado por escritura no atómica, y un cursor incremental que dejaba ceros de relleno fijos para siempre en reportes de generación), un aviso nuevo en la app para detectar reportes desactualizados respecto al último sync, y un primer paso de rediseño visual. Todos los cambios de código incluyen pruebas nuevas; la suite completa se corrió antes de cada commit.

**No se modificó `__version__` en `bess/__init__.py` ni se creó tag de release.** Este documento describe lo ya commiteado en `main`; el corte formal de la versión (bump + tag + build) queda pendiente de que decidas hacerlo.

## Cambios principales

### Protección de datos en syncs en vivo

- **`no_degradar_a_ceros` en los tres puntos de sync API/Modbus** (`iusasol/sync_db.py`, `granja/sync_db.py`, `ion/sync.py`): un lote entero en cero devuelto por una falla transitoria de la API o un glitch de lectura Modbus ya no pisa silenciosamente lecturas reales guardadas antes. Pasó en producción con Cogeneracion, GENERACION_ARAGON y Generacion_IUSA_2.
  → `tests/test_db_upsert_no_degradar_a_ceros.py` (6 pruebas)

### Escritura atómica en el pipeline

- **`bess/core/atomic_io.py`** (nuevo): `ruta_temporal_atomica()` escribe primero a un temporal en el mismo directorio y solo reemplaza el archivo final si la escritura completa sin excepción. Aplicado en los 8 escritores de reescritura completa/ventana del pipeline (`verify.py`, `clean.py`, `combined.py`, `granja.py`, `bess_daily.py`, `accumulated.py`, `daily.py`, `export_csv.py`).
- Antes de este cambio, una corrida interrumpida a medio escribir (crash, cierre forzado, `PermissionError`) dejaba el CSV de salida truncado permanentemente en un punto indetectable por inspección simple. Pasó en producción: `COMBINADO_POR_MINUTO_ION_Testigo_IUSA1_IUSA_1.csv` y los tres `*_Filtrado.csv` de IUSA_ARAGON perdieron más de un día de datos ya guardados.
- `export_csv.py` además gana el mismo manejo de `OSError` con mensaje amigable que ya tenían `verify.py`/`clean.py` (antes fallaba con traceback crudo si el CSV estaba abierto en Excel).
  → `tests/test_atomic_io.py` (7 pruebas)

### Aviso de reporte desactualizado

Investigando un reporte de "los datos se regresaron a una fecha vieja" en IUSA_1, el `sync_log` confirmó que la sincronización (fuente → SQLite) es puramente incremental y nunca retrocede. El hueco real: Verificar/Filtrar/Reportes es un paso manual separado que puede quedar atrás del sync sin ningún aviso en la app (p. ej. tras restaurar un respaldo y resincronizar sin volver a procesar).

- **`bess/ui/pipeline_status.py`**: `evaluar_desfase_reportes()` compara, por subestación, la última fecha en `sync_state` (SQLite) contra la última fecha ya escrita en su reporte combinado. `render_aviso_reporte_desactualizado()` muestra un aviso persistente si el desfase supera 3 horas. Se llama antes de mostrar cualquier gráfica/tabla en el reporteador.
- **Extensión**: el aviso originalmente solo revisaba el reporte de consumo (medidor de facturación). Se amplió para revisar también el reporte de generación (granja o cogeneración/individual) de cada subestación — caso real que se escapaba: GENERACION_ARAGON con su Filtrado al corriente pero su combinado congelado varias horas atrás, sin ningún aviso.
- **`bess/data/aggregates/combined.py`**: expone `ultima_fecha_hora_escrita()` (wrapper público, sin duplicar lógica) para que el aviso pueda leer la última fecha de cualquier reporte combinado.
  → `tests/test_pipeline_status_desfase.py` (9 pruebas)

### Reportes de generación: corrección de cursor incremental

Al usar el aviso anterior se detectó un cuarto bug real: el combinado de generación de Aragón (`COMBINADO_POR_MINUTO_GENERACION_ARAGON.csv`) se quedaba congelado en una hora vieja sin importar cuántas veces se corriera Reportes, mientras su Filtrado ya tenía datos reales varias horas más recientes.

- **Causa**: `_escribir_combinado_minuto()` en `bess/data/aggregates/granja.py` solo anexaba filas con fecha estrictamente posterior al cursor (última fila ya escrita). La fuente (API ISOL) rellena el día con ceros por adelantado y los reemplaza con datos reales conforme pasan las horas — la última fila ya escrita podía ser un cero de relleno de una hora *futura*, dejando el cursor por delante de datos reales que llegaban después para horas *anteriores* a esa. Como esas fechas nunca eran "más nuevas" que el cursor, el cero de relleno quedaba fijo para siempre.
- **Arreglo**: en vez de anexar, reescribe una ventana de los últimos días (mismo mecanismo que `combined.py` ya usa para el lado de consumo — funciones reutilizadas tal cual, sin duplicar lógica).
  → `tests/test_granja_relleno_ceros.py` (4 pruebas nuevas; las 5 pruebas ya existentes de `test_granja_incremental.py` siguen pasando sin cambios, confirmando que no hay regresión)

### Gráficas: rangos de eje Y

- **Tendencias** (`bess/charts/trends.py`): `graficar_tendencia_con_sin_bess` y `graficar_tendencia_bess_operacion` usaban un rango de eje Y fijo, calibrado a la escala de IUSA_1/IUSA_2. IUSA_ARAGON es ~400 veces más chico en consumo/BESS — con el rango fijo, su curva quedaba aplastada pegada al cero. El rango ahora se calcula dinámicamente desde el máximo real de los datos graficados (8% de margen).
  → `tests/test_trends_yaxis_range.py` (6 pruebas)
- **Perfil de carga** (`bess/charts/profile.py`), dos bugs distintos en `_rango_y_perfil()`, ambos confirmados con datos reales de IUSA_ARAGON:
  - Trataba "Demanda real" y "kW recibidos" como series mutuamente excluyentes al calcular el máximo, pero la gráfica las dibuja de forma independiente — en sitios con demanda real *y* consumo neto a la vez (caso ARAGON), el pico de "kW recibidos" se cortaba por arriba.
  - El límite inferior solo consideraba el mínimo de la demanda real, ignorando la magnitud de la descarga BESS graficada aparte — si la descarga bajaba más que la demanda real, esa línea se cortaba por abajo.
  → `tests/test_profile_yaxis_range.py` (6 pruebas)

### Interfaz: primer paso de rediseño visual

- **`bess/ui/styles.py`**: se quitaron sombras y degradados decorativos (tarjetas, panel de navegación, botones, callouts) a favor de un look plano. Sin cambios funcionales ni de paleta de colores semántica (Base/Intermedio/Punta, carga/descarga BESS se dejaron intactos). Primer paso de una serie acordada con el usuario; capas siguientes (tipografía, tarjetas de métricas) quedan pendientes.

## Incidente operativo (transparencia)

Durante esta sesión, al correr la suite de pruebas completa en el entorno de trabajo, varias pruebas de integración escribieron sobre archivos reales de `data/ArchivosProcesados` y `data/ArchivosReporte` de IUSA_1 (el entorno de trabajo usa la misma carpeta real del usuario, no una copia aislada). Al intentar revertir ese efecto secundario con `git checkout -- data/`, se sobrescribieron esos archivos reales con una versión vieja ya committeada en el repositorio (con datos solo hasta el 14/07), causando la confusión de "los datos se regresaron a una fecha vieja" que se investigó extensamente antes de encontrar la causa real. **La base de datos y los archivos fuente nunca se vieron afectados** — el incidente se corrigió corriendo el pipeline de nuevo (Verificar/Filtrar/Reportes), sin pérdida de datos reales. A partir de este punto, la suite completa se corre excluyendo explícitamente los archivos de prueba que escriben sobre `data/` real, y se usa la herramienta de lectura de archivos (no la shell) para verificar contenido cuando hay dudas de actualidad.

## Archivos nuevos

- `bess/core/atomic_io.py`
- `tests/test_db_upsert_no_degradar_a_ceros.py`
- `tests/test_atomic_io.py`
- `tests/test_trends_yaxis_range.py`
- `tests/test_profile_yaxis_range.py`
- `tests/test_pipeline_status_desfase.py`
- `tests/test_granja_relleno_ceros.py`

## Archivos modificados

- `bess/data/ingest/iusasol/sync_db.py`, `bess/data/ingest/granja/sync_db.py`, `bess/data/ingest/ion/sync.py`
- `bess/data/pipeline/verify.py`, `bess/data/pipeline/clean.py`
- `bess/data/aggregates/combined.py`, `bess/data/aggregates/granja.py`, `bess/data/aggregates/bess_daily.py`, `bess/data/aggregates/accumulated.py`, `bess/data/aggregates/daily.py`
- `bess/data/ingest/ion/export_csv.py`
- `bess/charts/trends.py`, `bess/charts/profile.py`
- `bess/ui/pipeline_status.py`, `bess/ui/pages.py`, `bess/ui/styles.py`

## Pruebas

38 pruebas nuevas en 7 archivos, más verificación de no regresión en la suite existente relevante (incluye comparación contra datos reales del repo donde ya existía esa práctica, p. ej. `test_granja_incremental.py`). Todas corridas antes de cada commit.

## Pendiente / no incluido en esta sesión

- Investigación separada, aún no iniciada: qué tan seguro es eliminar de raíz el relleno de ceros por adelantado de la API ISOL (en vez de solo corregir cómo el pipeline lo reescribe) — decidido explícitamente posponer por el alcance/riesgo más amplio.
- Migración CSV → base de datos: pausada antes de esta sesión, sigue pendiente.
- Rediseño visual: solo se aplicó la primera capa (aplanado). Tipografía y tarjetas de métricas quedan para una siguiente pasada.
- Bump de versión y tag de release: no se hizo; queda a tu criterio cuándo cortar 5.13.0 formalmente.

## Versión anterior

- **5.12.0** — Sección Emisiones CO₂ Scope 2 con PDF descargable.
