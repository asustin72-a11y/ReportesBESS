# Manual de catálogo — Alta de medidores y subestaciones

**Suite IUSASOL · BESS**  
**Versión:** 5.18.10  
**Audiencia:** superadministrador  
**Alcance:** reglas de negocio del catálogo y pasos para dar de alta un medidor o una subestación nueva

---

## 1. Quién puede hacerlo y dónde

Solo el rol **superadmin** puede editar el catálogo.

1. Inicie sesión en BESS con una cuenta superadmin.
2. En la barra lateral, abra **Catálogo** → **Administrar catálogo** (o la sección equivalente *Catálogo, tarifas y usuarios*).
3. Use las pestañas **Subestaciones**, **Medidores**, **Tipos**, **Validación**, **Cliente recibo** y **Usuarios** según el caso.

Los cambios viven en la base `bess_catalog.db` (tablas `catalog_*`). Al **Guardar en disco** se validan las reglas; si hay errores, no se guarda nada.

Botones de la barra superior:

| Botón | Efecto |
|-------|--------|
| **Validar catálogo** | Comprueba reglas sin guardar. Los errores se listan en la pestaña Validación. |
| **Guardar en disco** | Valida otra vez y, si todo es correcto, persiste subestaciones, tipos y medidores. |
| **Descartar cambios** | Recarga desde la base y pierde ediciones no guardadas. |

---

## 2. Conceptos del catálogo

### 2.1 Subestación

Cada sitio operativo (IUSA_1, IUSA_2, IUSA_ARAGON, …) es una fila en **Subestaciones**.

| Campo | Descripción |
|-------|-------------|
| `Numero` | Entero único (1, 2, 3…). Los medidores se vinculan con este número en `Subestacion`. |
| `Nombre` | Identificador interno (sin espacios raros; p. ej. `IUSA_1`). |
| `Generacion` | Modo de generación: `0`, `1` o `2` (ver sección 3). |
| `Esquema_Tarifa` | `DIST` o `GDMTH` (tarifas CFE / criterios de capacidad). |

### 2.2 Tipos de medidor

Definidos en **Tipos** (normalmente no se modifican en operación diaria):

| Tipo | Descripción | Uso típico |
|------|-------------|------------|
| 1 | Neteo | Medidor de facturación / testigo de red (ION u API) |
| 2 | Consumo | Banco u otro consumo auxiliar |
| 3 | BESS | Almacenamiento |
| 4 | GeneracionMultiple | MEGAs de granja solar (grupo) |
| 5 | GeneracionIndividual | Cogeneración, solar individual, Aragón, etc. |

### 2.3 Medidor

| Campo | Descripción |
|-------|-------------|
| `Nombre` | ID único del medidor (nombres de CSV, sync y reportes). Sin espacios preferible; use `_`. |
| `Numero_Serie` | Serie ISOL / API. Obligatorio si `Descarga=API`. |
| `Subestacion` | Número de la subestación (`1`, `2`, …). |
| `Tipo_Medidor` | 1–5 según la tabla anterior. |
| `Descarga` | `ION` (Modbus) o `API` (Ethernet / porteo). |
| `IP` | Obligatoria y distinta de `0` si `Descarga=ION`. |
| `Puerto` | Puerto Modbus (p. ej. `502`) o `0` si no aplica. |
| `Grupo_Generacion` | Obligatorio en tipo 4 cuando la subestación tiene `Generacion=1` (mismo nombre de grupo para todos los MEGAs, p. ej. `Generacion_IUSA_2`). Vacío en tipo 5. |
| `Validado` | Marca de última sync correcta (`dd/mm/aaaa HH:MM`). Puede quedar vacío al alta; se llena al sincronizar. |

---

## 3. Reglas de negocio (obligatorias)

El sistema **rechaza guardar** si alguna de estas reglas falla.

### 3.1 Por subestación

- Debe tener **al menos un** medidor asignado.
- Exactamente **1** medidor tipo **1** (Neteo / facturación).
- Al menos **1** medidor tipo **3** (BESS).
- Se permiten varios tipo 2 u otros auxiliares, según el sitio.

### 3.2 Modo `Generacion` de la subestación

| Valor | Significado | Medidores de generación permitidos |
|-------|-------------|--------------------------------------|
| `0` | Sin generación | Ningún tipo 4 ni tipo 5 |
| `1` | Grupo (granja) | Uno o más tipo **4**, todos con el mismo `Grupo_Generacion`; **sin** tipo 5 |
| `2` | Individual | Uno o más tipo **5** (p. ej. cogeneración + solar); **sin** tipo 4 |

### 3.3 Por medidor (origen de datos)

- `Descarga=ION` → `IP` válida (no vacía ni `0`).
- `Descarga=API` → `Numero_Serie` obligatorio.
- Tipo 4 en subestación con `Generacion=1` → `Grupo_Generacion` obligatorio.

### 3.4 Canal de energía (operación, no campo de catálogo)

Tras el alta, el pipeline usa:

- Tipo **4** (grupo / MEGAs): columna **`KWH_REC`**.
- Tipo **5** (individual): columna **`KWH_ENT`** (igual que Cogeneracion y GENERACION_ARAGON).

### 3.5 Participación Shapley (capacidad CFE)

Si la subestación tiene generación (`Generacion` 1 o 2), la pestaña **Participación** atribuye el ahorro de capacidad entre:

- **Cada recurso de generación** (granja agregada, o cada medidor tipo 5 por separado), y
- **BESS**.

Ejemplo IUSA_1 con dos tipo 5: participantes **Cogeneración · Solar · BESS** (3 jugadores). No hace falta configurar Shapley a mano: basta con que los medidores existan en catálogo y tengan reportes generados.

---

## 4. Pasos: dar de alta un medidor nuevo

Use este flujo cuando la **subestación ya existe** (p. ej. agregar solar individual a IUSA_1).

### 4.1 Preparar datos

Anote antes de editar:

1. `Nombre` definitivo (aparecerá en archivos y UI).
2. `Numero_Serie` (API) o `IP`/`Puerto` (ION).
3. `Subestacion` (número).
4. `Tipo_Medidor` y, si aplica, `Grupo_Generacion`.
5. Confirme que el modo `Generacion` de la subestación admite ese tipo (sección 3.2).

### 4.2 En la UI

1. Abra **Administrar catálogo**.
2. Si el medidor es de generación y la subestación aún está en `Generacion=0`, vaya primero a **Subestaciones** y cambie a `1` o `2` según el caso.
3. Pestaña **Medidores** → filtre por subestación si ayuda.
4. Agregue una **fila nueva** al final del editor.
5. Complete todos los campos requeridos.
6. Pulse **Validar catálogo**. Si hay errores, corríjalos (pestaña Validación).
7. Pulse **Guardar en disco**.

### 4.3 Después de guardar (datos y reportes)

1. **Sincronizar** el medidor (Paso a paso / Sincronizar ahora) para traer perfiles API o ION.
2. Confirme que `Validado` se actualizó (o que el sync reportó OK).
3. Ejecute en orden: **Verificar → Filtrar → Generar reportes**.
4. Revise la sección **Generación** (si aplica) y, con capacidad CFE, **Participación** (Shapley).

### 4.4 Ejemplo: solar individual en IUSA_1

IUSA_1 ya tiene `Generacion=2` y el medidor `Cogeneracion` (tipo 5). Para un segundo generador:

| Campo | Ejemplo |
|-------|---------|
| Nombre | `Solar_IUSA1` |
| Numero_Serie | *(serie real API)* |
| Subestacion | `1` |
| Tipo_Medidor | `5` |
| Descarga | `API` |
| IP / Puerto | `0` / `0` |
| Grupo_Generacion | *(vacío)* |

No cambie `Generacion` de la subestación (debe seguir en `2`). Tras sync y reportes, Shapley mostrará tres participantes.

### 4.5 Ejemplo: un MEGA más en IUSA_2

IUSA_2 tiene `Generacion=1`. Nueva fila tipo **4**, mismo `Grupo_Generacion` que el resto (`Generacion_IUSA_2`), `Descarga=API` y serie correcta.

---

## 5. Pasos: dar de alta una subestación nueva

Una subestación **no puede guardarse vacía**: el validador exige al menos el juego mínimo de medidores en la misma operación de guardado (o en un solo ciclo de edición antes de Guardar).

### 5.1 Diseño mínimo recomendado

| Rol | Tipo | Notas |
|-----|------|--------|
| Facturación / testigo | 1 | Exactamente uno. `ION` con IP o `API` con serie. |
| BESS | 3 | Al menos uno. Suele ser `API`. |
| Generación (opcional) | 4 o 5 | Solo si `Generacion` es 1 o 2. |

Opcionales: tipo 2 (banco/consumo), más de un BESS, varios tipo 5, etc.

### 5.2 Procedimiento

1. **Subestaciones** → fila nueva:
   - `Numero`: siguiente libre (p. ej. `4`).
   - `Nombre`: p. ej. `IUSA_NUEVA`.
   - `Generacion`: `0`, `1` o `2`.
   - `Esquema_Tarifa`: `DIST` o `GDMTH`.
2. **Medidores** → cree **todas** las filas mínimas con `Subestacion` = ese número.
3. Si `Generacion=1`, cree los tipo 4 con el mismo `Grupo_Generacion`.
4. Si `Generacion=2`, cree al menos un tipo 5.
5. **Validar catálogo** → corrija hasta cero errores.
6. **Guardar en disco**.
7. (Recomendado) Pestaña **Cliente recibo**: datos fiscales/servicio de la nueva subestación y **Guardar datos cliente** (botón propio de esa pestaña).
8. (Opcional) **Usuarios**: asigne acceso a la subestación si el modelo de permisos lo requiere.
9. Pipeline: **Sincronizar → Verificar → Filtrar → Generar reportes**.
10. Compruebe en el selector de subestación de BESS que el sitio aparece y tiene datos.

### 5.3 Checklist rápida (subestación nueva)

- [ ] Número y nombre únicos
- [ ] Exactamente 1 tipo 1
- [ ] ≥ 1 tipo 3
- [ ] Modo `Generacion` coherente con tipos 4/5
- [ ] ION con IP / API con serie
- [ ] Validar OK → Guardar
- [ ] Cliente recibo (si usarán recibo estimado)
- [ ] Sync + verificar + filtrar + reportes

---

## 6. Errores frecuentes

| Mensaje / síntoma | Qué revisar |
|-------------------|-------------|
| Debe tener exactamente 1 medidor tipo 1 | Falta el testigo/facturación o hay dos tipo 1. |
| Requiere al menos 1 medidor tipo 3 | Falta BESS. |
| Generacion=2 requiere al menos 1 tipo 5 | Puso modo individual sin medidor individual. |
| Generacion=1 no admite tipo 5 | Mezcló granja (4) e individual (5); elija un solo modo. |
| GeneracionMultiple sin Grupo_Generacion | Complete el grupo en todos los MEGAs. |
| API requiere Numero_Serie | Serie vacía en medidor API. |
| ION requiere IP válida | IP vacía o `0`. |
| Guardó bien pero no hay datos en Generación | Falta sync o el paso Generar reportes. |
| Shapley sigue en 2 participantes | El segundo tipo 5 no está en catálogo o no hay COMBINADO/perfil de ese medidor. |

---

## 7. Referencia rápida — sitios actuales

| Numero | Nombre | Generacion | Esquema | Generación en catálogo |
|--------|--------|------------|---------|-------------------------|
| 1 | IUSA_1 | 2 (individual) | DIST | `Cogeneracion` tipo 5 (+ solar tipo 5 cuando se dé de alta) |
| 2 | IUSA_2 | 1 (grupo) | DIST | MEGAs tipo 4, grupo `Generacion_IUSA_2` |
| 3 | IUSA_ARAGON | 2 (individual) | GDMTH | `GENERACION_ARAGON` tipo 5 |

---

## 8. Orden operativo después de cualquier alta

```
Catálogo (Validar → Guardar)
        ↓
Sincronizar perfiles (ION / API)
        ↓
Verificar → Filtrar → Generar reportes
        ↓
UI: Generación / Análisis / Participación (Shapley) / Recibo
```

No omita **Filtrar** ni **Generar reportes**: el catálogo solo declara el medidor; los CSV de reporte son los que alimentan gráficas y Shapley.
