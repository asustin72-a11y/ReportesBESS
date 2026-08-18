# Manual de usuario — Suite IUSASOL

**Versión:** 5.18.15  
**Aplicación:** Suite IUSASOL (portal de módulos de energía)

Este manual describe **todas las opciones** disponibles en la Suite para el usuario final: acceso, cada módulo y qué hace cada pantalla.  

> **PDF:** [`docs/MANUAL_SUITE.pdf`](MANUAL_SUITE.pdf) — regenerar con `python docs/generar_manual_suite_pdf.py`  
> Para operaciones avanzadas de base de datos y pipeline BESS, véase también [GUIA_ADMINISTRADOR.md](GUIA_ADMINISTRADOR.md).  
> Detalle histórico del reporteador BESS (con capturas): [GUIA_USUARIO.md](GUIA_USUARIO.md).

---

## 1. Qué es la Suite

La Suite IUSASOL es un portal con **una sola sesión** y **cinco módulos**:

| Grupo | Módulo en pantalla | Para qué sirve |
|-------|--------------------|----------------|
| **Operación** | **BESS** | Operación de batería, costos, recibo CFE, emisiones y PDF de planta |
| **Operación** | **Granja Solar** | Energía e ingresos DIST de los 21 MEGAs |
| **Herramientas** | **Descargas API** | Bajar perfiles crudos a CSV/ZIP desde la API |
| **Herramientas** | **Análisis de Perfil** | Analizar un perfil (T01 / GDMTH / DIST) y generar reportes |
| **Herramientas** | **Consultar Tarifa** | Consultar cuotas vigentes en CFE (app.cfe.mx) |

**Entrada habitual:** abrir la URL del servidor (o `streamlit run streamlit_app.py` en local).  
También puede abrirse cada módulo por separado (p. ej. `streamlit_bess.py`), pero desde la Suite se conserva la misma sesión.

---

## 2. Acceso y roles

### 2.1 Inicio de sesión

1. Abra la Suite.
2. Ingrese **Usuario** y **Contraseña**.
3. Pulse **Iniciar Sesión**.

Si las credenciales no son válidas verá: *Usuario o contraseña incorrectos*.

### 2.2 Roles

| Rol | Qué puede hacer en la Suite |
|-----|-----------------------------|
| **Visualizador** | Consultar módulos; en BESS **no** ve la barra lateral de pipeline |
| **Administrador** | Lo anterior + pipeline BESS (sincronizar, filtrar, reportes CSV) |
| **Superadministrador** | Lo anterior + catálogo BESS, mantenimiento DB y sync manual de Granja |

Los mismos usuarios sirven para todos los módulos de la Suite.

### 2.3 Selector de módulos

Tras el login:

- Encabezado **Suite IUSASOL** y su rol/nombre.
- Tarjetas de módulos (pulse el **título** de la tarjeta para entrar).
- **Cerrar sesión** — cierra la sesión completa.

Dentro de cualquier módulo:

- **Volver a la Suite** — regresa al selector **sin** cerrar sesión.
- **Cerrar sesión** — termina la sesión.

---

## 3. ¿Qué módulo uso?

| Necesidad | Módulo | Acción típica |
|-----------|--------|---------------|
| Ver carga/descarga BESS, costos, recibo o emisiones | **BESS** | Elegir subestación y medidor → sección |
| Actualizar datos de planta | **BESS** (Admin+) | **Procesar todo** o pasos de la barra lateral |
| Ver energía/ingresos de la granja | **Granja Solar** | **Dashboard** → periodo → **Consultar** |
| PDF de granja | **Granja Solar** → **Reportes** | Generar y **Descargar PDF** |
| Bajar CSV crudos de la API | **Descargas API** | Elegir fuente → **Generar descarga** |
| Analizar un perfil suelto (archivo o API) | **Análisis de Perfil** | Configurar → perfiles → **Generar reportes** |
| Ver cuota CFE vigente (Hogar/Negocio/…) | **Consultar Tarifa** | **Consultar en CFE** |
| Cambiar medidores, usuarios o tarifas BESS | **BESS** → Catálogo (Superadmin) | Guardar en disco |

---

## 4. Módulo BESS · Sistema de Energía

Reporteador de batería para subestaciones **IUSA 1**, **IUSA 2** e **IUSA ARAGON**.

### 4.1 Controles globales

| Control | Función |
|---------|---------|
| **Subestación** | Sitio a consultar |
| **Medidor** / **Medidor de Facturación** | Medidor de consumo/facturación de esa subestación |

La pantalla se refresca periódicamente (~15 min). Si los datos sincronizados son más recientes que el reporte CSV mostrado, puede aparecer un aviso de **desfase**: el administrador debe **Verificar → Filtrar → Generar reportes** (o **Procesar todo**).

### 4.2 Secciones del reporteador

Navegación superior (al pasar el cursor ~2 s se muestra la ayuda):

| Botón | Sección | Qué consulta |
|-------|---------|--------------|
| ⚡ **Operación** | Operación BESS | Carga, descarga, eficiencia, arbitraje, perfil y detalle por periodo |
| 📊 **Análisis** | Análisis | Demanda, costos de energía, capacidad CFE |
| ⚖️ **Participación** | Participación Capacidad | Atribución generación vs BESS (si aplica) |
| 📈 **Tendencia** | Tendencia | Histórico de consumo y operación BESS |
| ☀️ **Generación** | Generación | Recurso de generación (solo si la subestación lo tiene) |
| 📄 **Reportes** | Reportes | PDF diario y acumulado |
| 🧾 **Recibo** | Recibo CFE | Recibo estimado con/sin BESS |
| 🌿 **Emisiones** | Emisiones CO₂ | Huella Scope 2 y PDF |

#### Operación

- Fechas **Desde** / **Hasta** (métrica **Días**).
- Resumen: Carga BESS, Descarga BESS, Eficiencia, Arbitraje.
- Gráfica de **Perfil de carga** (descarga PNG disponible).
- Tabla **Detalle de Energía por Periodo** (Base / Intermedio / Punta).
- **Arbitraje por periodo** y su gráfica.

#### Análisis

- Fecha de corte.
- Subvistas: **Demanda**, **Energía y costos**, **Capacidad CFE**.

#### Participación

- **Fecha de corte**.
- Subvistas: Participación, Escenarios CFE, Shapley (MXN / kW), Metodología.
- Es informativa: no cambia los totales de Capacidad CFE del resto de la app.

#### Tendencia

- Rango **Desde** / **Hasta**.
- Vistas de consumo por periodo, con BESS y operación diaria.

#### Generación

- Visible solo con recurso de generación configurado.
- Si no hay datos: ejecutar pipeline (**Verificar → Filtrar → Reportes**).

#### Reportes (PDF)

- **Reporte diario:** fecha; opción de incluir generación en el perfil; **Generar Reporte Diario**.
- **Reporte acumulado:** fecha de corte; KPIs del periodo; **Generar Reporte Acumulado**.

#### Recibo CFE

- **Fecha de corte**.
- Escenario: **Sin BESS** / **Con BESS**.
- **Descargar recibo** (PDF).

#### Emisiones

- **Fecha de corte**.
- Comparación Con/Sin BESS y gráficas.
- **Descargar reporte de emisiones** (PDF).

### 4.3 Barra lateral (Administrador y Superadministrador)

Orden típico:

1. **Ayuda** — flujo: sincronizar → verificar/filtrar → generar CSV → consultar.
2. **⚡ Procesar todo** — ejecuta sync + verificar + filtrar + reportes.
3. **🔧 Paso a paso** — **Sincronizar ahora**, **Verificar**, **Filtrar**, **Generar reportes**.
4. **📂 Cargar archivos** — subir CSV fuente.
5. **💲 Consulta — Tarifas** — esquema DIST / GDMTH (consulta).
6. *(Superadmin)* **🏭 Catálogo** — subestaciones, medidores, tarifas, usuarios, validación.
7. *(Superadmin)* **🗄️ Mantenimiento DB** — importar/exportar, rebuild CSV, purgar, etc.

Si hay medidores pendientes de validación, **Procesar todo** puede bloquearse hasta corregir el catálogo.

---

## 5. Módulo Granja Solar

**Nombre en pantalla:** Reporteador Granja Solar IUSASOL.

Consulta energía e **ingresos DIST** de los 21 MEGAs. Los datos viven en la base de la Suite (sincronizados por cron o por el superadmin).

### 5.1 Secciones

Radio superior: **Dashboard** | **Reportes**.

### 5.2 Dashboard

**Periodo de consulta**

- Atajos: **Actual**, **Ayer**, **Mes actual**, **Mes ant.**, **Todo**.
- Fechas **Desde** / **Hasta**.
- Pulse **Consultar** para aplicar el rango (si cambia fechas sin consultar, la app lo indica).

**Contenido**

- KPIs: energía del periodo, ingreso DIST, acumulados o promedio diario.
- Gráficas por MEGA y, en rangos de varios días, resúmenes diarios.
- En un solo día: perfil de potencia estimado (MW).
- Tabla **Energía e ingreso por MEGA**.
- Caption con precios DIST del mes.

Si no hay perfiles: sincronizar (superadmin / cron).

### 5.3 Reportes

| Tipo | Botón | Resultado |
|------|-------|-----------|
| **Reporte Diario** | **Generar PDF diario** → **Descargar PDF** | Energía e ingresos del día |
| **Mensual Ingresos** | **Generar PDF de ingresos** → **Descargar PDF** | Mes de ingresos DIST |
| **Mensual Energía** | **Generar PDF de energía** → **Descargar PDF** | Mes de energía |

En diario: **◀ Día ant.**, **Día sig. ▶**, **Último día** y selector **Fecha**.

### 5.4 Sidebar (solo Superadministrador)

- **Sincronizar perfiles**
- Opciones: **Forzar fecha de inicio**, **Limitar fecha final**
- Botón **Sincronizar 21 MEGAs**
- Expander con el resultado de la última sincronización

---

## 6. Módulo Descargas API

**Nombre en pantalla:** Descarga de Perfiles IUSASOL.

Baja perfiles de la API IUSASOL a **CSV** (o **ZIP** si hay varios).  
**No** escribe la base BESS ni ejecuta el pipeline de planta.

Caption de ayuda: *Clientes = ISOL · Granja = Farm · Porteo = Reports/Porteo.*

### 6.1 Secciones

| Sección | Fuente | Contenido típico del CSV |
|---------|--------|--------------------------|
| **Clientes (ISOL)** | ISOL | Fecha, KWH_REC, KWH_ENT, KVARH_Q1…Q4 |
| **Granja (Farm)** | Farm | Fecha, kwh_rec |
| **Porteo** | Porteo | Mismo layout que Clientes |

### 6.2 Cómo descargar

1. Elija la sección (Clientes / Granja / Porteo).
2. Defina **Desde** y **Hasta**.
3. Seleccione **Medidores** (multiselección).
4. Pulse **Generar descarga**.
5. Pulse **Descargar …** cuando esté listo.

Si falla el listado de medidores: **Reintentar listado**.

**Avisos frecuentes**

- La API no devolvió medidores (credenciales o red).
- En Granja: 1 petición por día y medidor; rangos muy grandes pueden tardar o advertir por volumen de requests.

---

## 7. Módulo Análisis de Perfil

Analiza perfiles cincominutales (archivo o API) con tarifas **01**, **GDMTH** o **DIST**, y genera CSV, PNG y PDF.

### 7.1 Configuración

1. **Tarifa**
   - `0 — Tarifa 01 (doméstica)`
   - `1 — GDMTH (horaria)`
   - `2 — DIST (horaria)`
2. **Servicio:** Consumo · Generación · Bidireccional · Neteo.
3. Si DIST/GDMTH: elija **Región** (división) y, si hace falta, **Sincronizar tarifas CFE**.
4. Opcional: **Mostrar desglose completo**.
5. **Limpiar** reinicia la configuración (expander **Ayuda rápida** disponible).

### 7.2 1. Perfiles

Origen: **Subir archivo** o **Descargar de API**.

- Archivo: **Seleccionar CSV o ZIP**; factor numérico; **Canales invertidos** si aplica.
- API: **Fuente API** (Clientes / Granja / Porteo), fechas, medidores, **Obtener perfiles**.
- Opcional: **Analizar solo un subintervalo** con **Desde** / **Hasta**.

### 7.3 2. Generar reportes

- Pulse **Generar reportes**.
- Revise calidad de datos (cobertura, huecos) y métricas en pantalla.

### 7.4 3. Resultados

Pestañas:

| Pestaña | Contenido |
|---------|-----------|
| **Diario / Mensual** | Energía por día/mes, perfil sumado |
| **Típicos** | Consumo típico semanal y tipico día×hora |
| **Por hora** | Energía por hora |
| **Gráficas** | PNG comparativa y por día |

Descargas principales:

- **Descargar todo (ZIP)**
- **Descargar CSV recibo-ready**
- **Descargar reporte PDF**
- Descargas individuales por archivo en cada pestaña

**Nota:** si reinicia la sesión, los CSV generados y no descargados se pierden.

---

## 8. Módulo Consultar Tarifa

Consulta **cuotas vigentes** en `app.cfe.mx` (solo lectura: no modifica SQLite ni el catálogo BESS).

Subtítulo de referencia: *Cuotas CFE · Hogar · Negocio · Industria · Agrícola*.

### 8.1 Secciones

Radio: **Consulta** | **Reportes CSV**.

### 8.2 Consulta — «Consultar cuota vigente»

1. **Categoría:** Hogar · Negocio · Industria · Agrícola.
2. **Tarifa** (según categoría).
3. **Año** y **Mes**.
4. Si aplica: **Inicio temporada verano**.
5. Si la tarifa pide región:
   - **Cargar estados CFE** → **Estado**
   - **Cargar municipios** → **Municipio**
   - **Cargar divisiones** → **División**
   - **Etiqueta de tabla (opcional)**
6. Pulse **Consultar en CFE**.

En la barra lateral hay un expander de **Tarifas disponibles**.

### 8.3 Reportes CSV

- Elija **Periodo**.
- Descargue los CSV ya generados en el servidor (si existen).  
  Si no hay archivos, el módulo lo indica; la generación masiva suele hacerse con script/cron aparte, no desde esta pantalla de consulta.

---

## 9. Entregables (PDF / CSV / ZIP)

| Entrega | Dónde |
|---------|-------|
| PDF diario / acumulado BESS | BESS → **Reportes** |
| PDF recibo CFE | BESS → **Recibo** |
| PDF emisiones | BESS → **Emisiones** |
| PNG de gráficas BESS | Botones de descarga en varias secciones |
| PDF diario / mensual granja | Granja → **Reportes** |
| CSV/ZIP perfiles API | **Descargas API** |
| ZIP / CSV / PDF de análisis | **Análisis de Perfil** |
| Cuota CFE en pantalla (+ CSV locales) | **Consultar Tarifa** |

---

## 10. Buenas prácticas y problemas frecuentes

1. **Empiece por el selector** y use **Volver a la Suite** para cambiar de módulo sin cerrar sesión.
2. En BESS, si las gráficas no reflejan lo recién sincronizado, pida al admin regenerar reportes (aviso de desfase).
3. En Granja, siempre pulse **Consultar** después de cambiar fechas.
4. En Descargas / Análisis vía API, acorte rangos si la descarga tarda demasiado.
5. En Análisis de Perfil, **descargue el ZIP** antes de cerrar sesión.
6. Consultar Tarifa necesita salida a internet hacia CFE; si falla, reintente o revise la red del servidor.
7. En pantallas angostas (móvil/tablet), la barra de sesión y los controles se apilan; las tablas permiten desplazamiento horizontal.

---

## 11. Documentación relacionada

| Documento | Audiencia |
|-----------|-----------|
| [GUIA_USUARIO.md](GUIA_USUARIO.md) | Detalle BESS con capturas |
| [GUIA_ADMINISTRADOR.md](GUIA_ADMINISTRADOR.md) | Pipeline, catálogo, DB |
| [DOCKER.md](DOCKER.md) | Despliegue en servidor |
| [RESTAURACION_LOCAL.md](../RESTAURACION_LOCAL.md) | Respaldo/restauración local |
| [INDICE_DOCUMENTACION.md](INDICE_DOCUMENTACION.md) | Índice general |

---

*Suite IUSASOL v5.18.15 — Manual de usuario*
