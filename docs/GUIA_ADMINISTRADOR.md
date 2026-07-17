# Guía del administrador — Sistema BESS

**Versión:** 5.14.0  
**Roles:** `admin` (operador) y `superadmin`

> **PDF:** `docs/GUIA_ADMINISTRADOR.pdf`  
> **Generar:** `python docs/generar_guia_admin_pdf.py`

---

## 1. Responsabilidades del administrador

El administrador mantiene el **pipeline de datos** que alimenta el reporteador:

1. **Sincronizar** perfiles (ION Modbus + medidores API: BESS, banco, generación).
2. **Verificar** que los CSV fuente estén en `data/ArchivosFuente/{Subestación}/`.
3. **Filtrar** la intersección temporal ION ∩ BESS (y generación si aplica).
4. **Generar reportes** CSV en `data/ArchivosReporte/`.

Los usuarios con rol **visualizador** (`user`) solo consultan el reporteador; no ven la barra lateral.

---

## 2. Acceso y roles

| Rol | Sidebar | Reporteador | Catálogo / BD |
|-----|---------|-------------|---------------|
| `user` | Oculta | Todas las secciones visibles para la subestación | No |
| `admin` | Pipeline completo | Sí | No |
| `superadmin` | Pipeline + Catálogo + Mantenimiento DB | Sí | Sí |

Credenciales por defecto (cambiar en producción): ver `README.md` o catálogo de usuarios en SQLite.

---

## 3. Barra lateral — orden de uso

Tras iniciar sesión como **admin** o **superadmin**, la sidebar muestra (de arriba hacia abajo):

### 3.1 Ayuda

Primer expander. Resume el flujo en cuatro pasos:

1. Sincronizar perfiles  
2. Verificar y filtrar datos  
3. Generar reportes CSV  
4. Consultar en el reporteador  

No ejecuta acciones; es referencia rápida.

### 3.2 ⚡ Procesar todo

Botón principal. En un solo paso ejecuta:

- Verificar datos fuente  
- Filtrar  
- Generar todos los reportes CSV  

**Requisito:** todos los medidores deben estar **validados** tras la última sincronización. Si hay pendientes, el botón muestra error y debe usar **Sincronizar** en Paso a paso primero.

Tras un proceso exitoso aparece un **banner** en la sidebar indicando que los reportes están listos.

### 3.3 🔧 Paso a paso

Expander con acciones individuales:

| Acción | Qué hace |
|--------|----------|
| **Sincronizar ahora** | Ejecuta `scripts/sincronizar_perfiles.py` (ION + API). Muestra resumen y actualiza validación de medidores. El último paso (SQLite → ArchivosFuente) es incremental: recalcula y reescribe una ventana del último día de historia (no solo lo estrictamente nuevo) y anexa lo que quede después de esa ventana, en vez de reexportar el histórico completo cada vez -- así se recogen correcciones que la API trae después para el día en curso. Un re-export explícito de un rango puntual (reparación de datos) sigue sobrescribiendo el archivo completo. |
| **Verificar** | Comprueba CSV en fuente y copia a procesados. Incremental: si ya existe un CSV procesado, solo verifica (duplicados + huecos) una ventana del último día de historia y la reemplaza, en vez de reprocesar todo el histórico -- esto recoge valores que el origen actualiza para el día en curso (p.ej. ION completando con datos reales un día que se había exportado primero en cero). La primera vez (o si cambia el formato de columnas) procesa completo, como antes. El día opera de 00:05 a 00:00 del día siguiente (288 perfiles/día, el 00:00 es el cierre del día anterior); si falta ese perfil dentro del rango de datos reales, se rellena con cero como cualquier otro hueco, sin excepción por fuente (ION incluido). El consolidado BESS (suma de medidores tipo BESS por subestación) usa el mismo esquema de ventana. |
| **Filtrar** | Genera archivos `*_Filtrado.csv` (intersección temporal). Ya no borra `ArchivosFuente` al terminar: ese archivo debe persistir para que la exportación incremental (paso "Sincronizar ahora") tenga cursor la próxima vez. Incremental: si el archivo filtrado ya existe, recalcula y reemplaza una ventana del último día de historia (no solo el tramo estrictamente nuevo), en vez de recalcular y reescribir todo el histórico filtrado en cada corrida. La primera vez (o si cambia el formato de columnas) procesa completo, como antes. |
| **Generar reportes** | Ejecuta `scripts/run_reporte_bess.py` con barra de progreso. El combinado por minuto (`COMBINADO_POR_MINUTO_*.csv`, el que calcula demanda rodante de 15 min y periodos CFE) es incremental: si ya existe con cursor legible y columnas compatibles, recalcula y reemplaza una ventana del último día de historia -- incluyendo el contexto necesario para que la demanda rodante no cambie de resultado -- en vez de solo anexar filas nuevas, para recoger correcciones que el origen trae para fechas ya combinadas. El diario (`ENERGIA_*_POR_DIA.csv`) también es incremental: cada día es independiente, así que solo se recalcula el último día ya escrito (por si seguía abierto) más los días nuevos; los días ya cerrados no se tocan. Los acumulados (`ACUMULADOS_*.csv`) también son incrementales: heredan el cumsum y el máximo corrido del día anterior (si es del mismo mes) y solo recalculan desde el último día ya escrito. El diario de BESS (`ENERGIA_BESS_*_POR_DIA.csv`) usa el mismo esquema incremental que el diario general. Los reportes de generación/granja (`COMBINADO_POR_MINUTO_Generacion_*.csv` y `ENERGIA_Generacion_*_POR_DIA.csv`, subestación IUSA 2) también son incrementales, con la misma lógica de ventana y de "último día se recalcula por si seguía abierto". |

Use este modo cuando necesite diagnosticar en qué paso falló el pipeline.

### 3.4 📂 Cargar archivos

Subida manual de CSV a `ArchivosFuente`. Útil si un archivo llegó por correo o USB en lugar de sync automático.

- Acepta múltiples archivos.  
- El nombre debe coincidir con el medidor del catálogo (ej. `ION_Testigo_IUSA1.csv`).  
- Tras subir, el sistema sugiere **Verificar** o **Procesar todo**.

### 3.5 💲 Consulta — Tarifas

Solo lectura: tarifas del **mes calendario actual** (Base, Intermedio, Punta, Capacidad, etc.).

La edición de tarifas es exclusiva del **superadmin** en el catálogo.

### 3.6 🏭 Catálogo (solo superadmin)

Acceso a la UI de administración:

- **Subestaciones:** identidad y esquema tarifario.
- **Tipos medidor:** clasificación y comportamiento de los medidores.
- **Medidores:** nombre, serie, fuente, subestación y parámetros operativos.
- **Tarifas:** valores mensuales Base/Intermedio/Punta, capacidad y cargos.
- **Cliente recibo:** datos fiscales/comerciales usados por el recibo CFE.
- **Usuarios:** altas, roles, contraseña, activación/desactivación.
- **Validación:** estado del catálogo antes de usar el pipeline.

La barra superior permite guardar o descartar cambios. Debe quedar al menos un
superadmin activo; el último superadmin no puede desactivarse, eliminarse ni
cambiar su propio rol sin que exista otro.

Botón alterna entre **Administrar catálogo** y **Volver al reporteador**.

### 3.7 🗄️ Mantenimiento DB (solo superadmin)

Esta sección administra `data/bess_perfiles.db` y la cadena CSV derivada. Solo
el rol `superadmin` puede abrirla. El rol `admin` conserva el pipeline, pero no
puede importar, purgar, alinear cursores, reconstruir CSV ni vaciar perfiles.

#### 3.7.1 Resumen, `sync_log` y cursores

- **Medidores registrados:** cantidad de filas, rango disponible,
  `sync_state.ultima_fecha` y hora de la última sincronización correcta.
- **Últimas sincronizaciones:** `sync_log` registra ION, API ISOL y Granja con
  inicio/fin, rango solicitado, registros leídos/insertados/actualizados,
  estado `ok`/`error` y mensaje de error.
- **Evaluar cursores:** compara `sync_state` con
  `data/Tarifas/Ultima_Sincronizacion.csv`.
- **Alinear a BD:** pone ambos cursores en `MAX(fecha)` de `perfil_carga`.
  Úselo cuando el CSV quedó atrás y provocaría una redescarga innecesaria.

> Alinear a BD no cambia perfiles de energía. Sí cambia desde dónde comenzará
> la próxima petición incremental.

#### 3.7.2 Importar CSV a SQLite

Formato esperado: `Fecha`, `KWH_REC`, `KWH_ENT`, `KVARH_Q1`…`KVARH_Q4`.

1. Seleccione el medidor destino.
2. Active **Solo timestamps faltantes** si no desea actualizar filas existentes.
3. Use **Sin filtro 00:05** solo para backfill que deba conservar el primer
   registro del día aunque no sea 00:05.
4. Opcional: active **Rebuild CSV después del import** y seleccione la fecha
   inicial de reconstrucción.
5. Suba el CSV y pulse **Importar a SQLite**.

Al terminar correctamente:

- las filas se guardan con `fuente=csv`;
- `sync_state` y `Ultima_Sincronizacion.csv` se alinean a `MAX(fecha)` en BD;
- el sync API, aunque traiga días completos, no pisa filas `csv` con energía
  real (`respetar_fuente=csv` + `no_degradar_a_ceros`);
- una fila `csv` totalmente en cero sí puede ser corregida posteriormente por
  la API.

Sin Rebuild, la importación actualiza SQLite pero no necesariamente los CSV que
lee el reporteador. Marque Rebuild cuando necesite reflejar la corrección de
inmediato en gráficas, emisiones, recibo CFE y reportes PDF.

#### 3.7.3 Exportar

- **Descargar CSV:** exporta un medidor, con rango opcional.
- **Exportar todos a ArchivosFuente:** reexporta los destinos configurados a
  `data/ArchivosFuente/{Subestación}/`.
- Una exportación explícita con fecha reemplaza el archivo Fuente desde esa
  fecha; no modifica `perfil_carga`.

#### 3.7.4 Reconciliar SQLite ↔ Fuente

Herramienta de solo lectura. Compara por medidor y día:

- `SUM(kwh_rec)`, `SUM(kwh_ent)` y número de filas en SQLite;
- los mismos valores en `ArchivosFuente`.

La interfaz usa una tolerancia de **0.05 kWh** y clasifica diferencias como
**faltan en Fuente**, **solo en Fuente** o **suma kWh distinta**. El rango
predeterminado es 45 días. Si detecta una divergencia, permite abrir Rebuild con
el medidor y el primer día afectado preseleccionados.

#### 3.7.5 Rebuild CSV forzado

Se usa cuando SQLite tiene datos correctos, pero Fuente/Procesados/Filtrado/
COMBINADO conservan huecos o ceros históricos que quedaron fuera de la ventana
incremental de un día.

El Rebuild:

1. **Lee** SQLite y reexporta el medidor a `ArchivosFuente` desde la fecha
   seleccionada.
2. Borra únicamente los CSV derivados aplicables: procesado individual,
   consolidado BESS, filtrado, combinado, energía diaria y acumulados.
3. Opcionalmente ejecuta **Verificar → Filtrar → Reportes**.

No borra ni modifica `perfil_carga` o `sync_state`. Antes de ejecutar, use
**Vista previa** y revise los archivos candidatos.

> La Fuente del medidor se reescribe desde la fecha elegida. Elija el primer
> día que deba conservar/reparar; no use una fecha posterior al inicio del tramo.

#### 3.7.6 Purgar

Dos modos:

- **Rango de fechas:** elimina solo el intervalo seleccionado.
- **Desde una fecha hasta el final:** elimina la cola y retrocede
  `sync_state`, preparando una resincronización incremental.

Siempre use **Vista previa** y marque la confirmación antes de borrar.

#### 3.7.7 Avanzado

- **Inicializar esquema y catálogo:** crea tablas faltantes.
- **Migrar IDs legacy:** ejecutar primero en modo dry-run.
- **Vaciar todos los perfiles:** borra `perfil_carga` y `sync_state`, conserva
  catálogo/usuarios/tarifas y exige escribir `VACIAR`.

Estas operaciones no tienen rollback global. Antes de purgar o vaciar, respalde
`data/bess_perfiles.db`.

### 3.8 Responsabilidades exclusivas del superadmin

- Mantener subestaciones, medidores, tarifas, clientes de recibo y usuarios.
- Conservar al menos un superadministrador activo; el sistema impide dejar la
  instalación sin uno.
- Revisar `sync_log`, cursores y reconciliación antes de una reparación.
- Preferir Rebuild CSV cuando SQLite está bien; purgar/re-sincronizar solo si
  la propia BD está incorrecta.
- Cambiar credenciales iniciales y no compartir el acceso superadmin.

---

## 4. Subestaciones soportadas

| Subestación | Medidor testigo / facturación | BESS | Generación |
|-------------|------------------------------|------|------------|
| **IUSA 1** | ION + Banco 1 | BESS_NORTE | Generación (API CS1305) |
| **IUSA 2** | ION testigo | BESS_SUR | Granja solar (Mega01–20) |
| **IUSA ARAGON** | Consumo Aragón | BESS Aragón | Generación Aragón |

El catálogo en SQLite es la fuente de verdad; los CSV en `data/Tarifas/` migran al primer arranque si las tablas están vacías.

---

## 5. Reporteador sin datos

Si aún no hay `COMBINADO_POR_MINUTO_*.csv`, el área principal muestra:

- Título **Reporteador sin datos**  
- Cuadro del flujo de trabajo (mismo contenido que Ayuda)  
- Aviso si faltan medidores por validar  

El operador debe completar el pipeline antes de que los visualizadores consulten gráficas.

Si aparece el aviso **“El reporte mostrado no incluye los datos ya
sincronizados más recientes”**, la app detectó más de 3 horas entre
`sync_state` y el último combinado. Primero ejecute **Procesar todo**. Si el
aviso persiste, el superadmin debe usar **Reconciliar** y, si procede,
**Rebuild CSV**.

---

## 6. Reglas de negocio importantes

### Participación Capacidad (Shapley)

- La atribución **generación vs BESS** solo se muestra en la sección **Participación Capacidad**.  
- **No** se propaga el ahorro de generación a Capacidad CFE, sidebar, PDF global ni métricas del dashboard.  
- El **reporte acumulado** puede incluir la parte Shapley **solo del BESS**.

### Banco 1 (IUSA 1)

- Intercambio REC/ENT solo en `Banco_1_Filtrado.csv`; `Banco_1.csv` no se modifica en filtrado.

### Consumo energético

- IUSA 2: columna `KWH_NETO` en consumo.  
- IUSA 1: columna `KWH_REC`.  
- Generación individual (tipo 5): `KWH_ENT`; granja solar agregada (tipo 4): `KWH_REC`.

---

## 7. Autorefresh

La aplicación recarga datos automáticamente cada **15 minutos** (`streamlit-autorefresh`). No sustituye ejecutar el pipeline cuando hay archivos nuevos en fuente.

---

## 8. Solución de problemas

| Síntoma | Acción |
|---------|--------|
| «Medidores sin validar» | Ejecutar **Sincronizar ahora**; revisar conectividad ION/API. |
| «Faltan archivos filtrados» | Ejecutar **Filtrar** antes de generar reportes. |
| Error al escribir CSV de reporte | Cerrar Excel u otros programas con archivos abiertos en `ArchivosReporte`. |
| Timeout en generación (>15 min) | Ejecutar `python scripts/run_reporte_bess.py` en consola del servidor. |
| Visualizador no ve datos | Confirmar que **Procesar todo** terminó OK para su subestación/medidor. |
| «Otra ejecución del pipeline sigue en curso» | Sincronizar/Verificar/Filtrar/Generar reportes están bloqueados entre sí (lock de archivo en `data/.pipeline.lock`) para no pisarse. Espere a que termine la otra ejecución (cron, otro admin, u otra pestaña) y reintente. |
| Reporte desactualizado (>3 h) | Procesar todo; si persiste, Reconciliar SQLite ↔ Fuente y usar Rebuild CSV. |
| BD tiene energía pero la gráfica muestra ceros históricos | Superadmin: Reconciliar → abrir Rebuild desde el primer día afectado. |
| `Ultima_Sincronizacion` difiere de `sync_state` | Resumen → Evaluar cursores; revisar y Alinear a BD. |
| Importé CSV pero la gráfica no cambió | Ejecutar Rebuild CSV del medidor o marcar Rebuild durante la importación. |

---

## 9. Archivos y rutas clave

```
data/
  ArchivosFuente/{Sub}/     ← CSV crudos (sync o carga manual)
  ArchivosProcesados/{Sub}/ ← Verificados y filtrados
  ArchivosReporte/{Sub}/    ← Combinados, energía diaria, acumulados
  Tarifas/                  ← CSV legacy (migración a SQLite)
  bess_catalog.db           ← Catálogo, tarifas, usuarios (SQLite)
  bess_perfiles.db          ← Perfiles, sync_state y sync_log (SQLite)
```

Cursores:

- `bess_perfiles.db::sync_state` — último perfil confirmado por medidor.
- `data/Tarifas/Ultima_Sincronizacion.csv` — inicio de la siguiente petición.
- La última fecha de cada CSV Fuente/Procesado/Reporte — cursor implícito de
  las etapas incrementales.

Scripts:

- `scripts/sincronizar_perfiles.py` — sync ION + API  
- `scripts/run_reporte_bess.py` — generación masiva de reportes  
- `scripts/limpiar_relleno_futuro.py` — diagnóstico/limpieza de slots futuros
- `scripts/purgar_api_desde.py` — purga desde fecha y ajuste de cursor

---

## 10. Soporte y despliegue

- Docker: [DOCKER.md](DOCKER.md)  
- Restauración local: [RESTAURACION_LOCAL.md](../RESTAURACION_LOCAL.md)  
- Versión 5.14.0: [RELEASE_NOTES_5.14.0.md](../RELEASE_NOTES_5.14.0.md)
- Versión 5.13.0: [RELEASE_NOTES_5.13.0.md](../RELEASE_NOTES_5.13.0.md)
- Versión 5.12.0: [RELEASE_NOTES_5.12.0.md](../RELEASE_NOTES_5.12.0.md)
- Versión 5.9.0: [RELEASE_NOTES_5.9.0.md](../RELEASE_NOTES_5.9.0.md)
- Versión 5.8.0: [RELEASE_NOTES_5.8.0.md](../RELEASE_NOTES_5.8.0.md)  

---

*Guía para administradores del sistema BESS — IUSASOL.*
