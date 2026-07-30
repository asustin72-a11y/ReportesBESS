# Descarga de Perfiles IUSASOL

Módulo hermano de BESS / Granja para bajar perfiles de la API a **CSV**
(sin escribir SQLite ni alimentar el pipeline de reportes).

## Secciones

| UI | API | CSV |
|----|-----|-----|
| **Clientes** | `Reports/ISOL/Meters` + `Profiles/Gral` | `Fecha,KWH_REC,KWH_ENT,KVARH_Q1…Q4` |
| **Granja** | `Reports/Farm…` (1 request/día/medidor) | `Fecha,kwh_rec` |
| **Porteo** | `Reports/Porteo/Meters` + `Meter/Profiles` | mismo layout que Clientes |

Auth OAuth API: la misma que BESS (`[iusasol]`). Login de usuarios: **desactivado** en el entry standalone; en la suite usa la sesión BESS.

## Suite BESS

Integrado en la app principal del repo BESS (`streamlit_app.py` / `bess/ui/pages.py`):

- Botón **📥 Descargas** en la barra superior (todos los roles: user / admin / superadmin).
- Botón **Volver al reporteador** cuando el panel de descargas está activo.
- Expander **Descargas API** en el sidebar de operadores (admin / superadmin).
- Orden de la barra superior: `[Descargas]` · `Volver a la Suite` (si aplica) · `Cerrar sesión`.

También sigue disponible el entry standalone:

```bash
streamlit run streamlit_descargas.py
```

1. Iniciar sesión (en la suite) o abrir el entry standalone.
2. Elegir sección (Clientes / Granja / Porteo).
3. Rango de fechas + medidores.
4. **Generar descarga** → **Descargar** (CSV o ZIP si hay varios medidores).

## Estructura

```text
descargas/
  porteo_client.py   # cliente Porteo
  export_csv.py      # JSON/perfiles → CSV
  service.py         # listar + descargar
  ui/                # Streamlit
streamlit_descargas.py
```

## Notas

- Granja con rangos largos × muchos MEGAs puede tardar (aviso en UI).
- Porteo verificado en vivo (2026-07-30): 6 canales como ISOL.
