# Guía del administrador — Sistema BESS

**Versión:** 5.9.0  
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
| **Sincronizar ahora** | Ejecuta `scripts/sincronizar_perfiles.py` (ION + API). Muestra resumen y actualiza validación de medidores. El último paso (SQLite → ArchivosFuente) es incremental: solo exporta las filas nuevas desde la última sincronización y las anexa al CSV existente, en vez de reexportar el histórico completo cada vez. Un re-export explícito de un rango puntual (reparación de datos) sigue sobrescribiendo el archivo completo. |
| **Verificar** | Comprueba CSV en fuente y copia a procesados. Incremental: si ya existe un CSV procesado, solo verifica (duplicados + huecos) las filas nuevas desde la última sincronización y las agrega al final, en vez de reprocesar todo el histórico. La primera vez (o si cambia el formato de columnas) procesa completo, como antes. El día opera de 00:05 a 00:00 del día siguiente (288 perfiles/día, el 00:00 es el cierre del día anterior); si falta ese perfil dentro del rango de datos reales, se rellena con cero como cualquier otro hueco, sin excepción por fuente (ION incluido). El consolidado BESS (suma de medidores tipo BESS por subestación) también es incremental: solo suma y anexa las filas nuevas. |
| **Filtrar** | Genera archivos `*_Filtrado.csv` (intersección temporal). Ya no borra `ArchivosFuente` al terminar: ese archivo debe persistir para que la exportación incremental (paso "Sincronizar ahora") tenga cursor la próxima vez. Incremental: si el archivo filtrado ya existe, solo calcula y anexa el tramo de fechas comunes que todavía no se había escrito, en vez de recalcular y reescribir todo el histórico filtrado en cada corrida. La primera vez (o si cambia el formato de columnas) procesa completo, como antes. |
| **Generar reportes** | Ejecuta `scripts/run_reporte_bess.py` con barra de progreso. El combinado por minuto (`COMBINADO_POR_MINUTO_*.csv`, el que calcula demanda rodante de 15 min y periodos CFE) es incremental: si ya existe con cursor legible y columnas compatibles, solo procesa y anexa las filas nuevas -- incluyendo el contexto necesario para que la demanda rodante no cambie de resultado. El diario (`ENERGIA_*_POR_DIA.csv`) también es incremental: cada día es independiente, así que solo se recalcula el último día ya escrito (por si seguía abierto) más los días nuevos; los días ya cerrados no se tocan. Los acumulados siguen recalculándose completos en cada corrida. |

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

- Subestaciones y medidores  
- Tarifas por mes  
- Usuarios y roles  

Botón alterna entre **Administrar catálogo** y **Volver al reporteador**.

### 3.7 🗄️ Mantenimiento DB (solo superadmin)

Herramientas SQLite: importar/exportar perfiles, purga de datos históricos, diagnóstico de BD.

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

---

## 9. Archivos y rutas clave

```
data/
  ArchivosFuente/{Sub}/     ← CSV crudos (sync o carga manual)
  ArchivosProcesados/{Sub}/ ← Verificados y filtrados
  ArchivosReporte/{Sub}/    ← Combinados, energía diaria, acumulados
  Tarifas/                  ← CSV legacy (migración a SQLite)
  bess_catalog.db           ← Catálogo, tarifas, usuarios (SQLite)
```

Scripts:

- `scripts/sincronizar_perfiles.py` — sync ION + API  
- `scripts/run_reporte_bess.py` — generación masiva de reportes  

---

## 10. Soporte y despliegue

- Docker: [DOCKER.md](DOCKER.md)  
- Restauración local: [RESTAURACION_LOCAL.md](../RESTAURACION_LOCAL.md)  
- Versión 5.9.0: [RELEASE_NOTES_5.9.0.md](../RELEASE_NOTES_5.9.0.md)
- Versión 5.8.0: [RELEASE_NOTES_5.8.0.md](../RELEASE_NOTES_5.8.0.md)  

---

*Guía para administradores del sistema BESS — IUSASOL.*
