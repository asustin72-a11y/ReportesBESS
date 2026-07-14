# BESS 5.7.0

## Resumen

Sección Generación, mejoras visuales en Mantenimiento BD, fix de logout limpio y zona horaria correcta en auditoría.

## Cambios principales

### Nueva sección: Generación
- Pestaña **Generación** entre Tendencia y Reportes.
- Gráfica de línea (día único) o barras apiladas (rango) según selección de fechas.
- Tabla resumen de energía por periodo horario con acumulado mensual.
- IUSA 1: Cogeneración (`KWH_ENT`); IUSA 2: Granja solar (`KWH_REC`).

### Logout limpio (sin residuos)
- Flujo de cierre de sesión rediseñado: flag `_logout_pendiente` + doble `st.rerun()`.
- Eliminación de `@st.fragment(run_every=...)` que causaba persistencia de DOM.
- CSS para ocultar tooltips de navegación (`#bess-nav-tooltip-root`) en pantalla de login.

### Mantenimiento BD — rediseño visual
- Cabecera con gradiente, indicadores de estado y tarjetas informativas.
- Tabs con iconos, spinners en operaciones, logs en expanders.
- Botón toggle "Abrir herramientas BD / Volver al reporteador" con cambio inmediato.

### Zona horaria en auditoría BD
- Timestamps de sincronización (`ultima_sync_ok`, `started_at`, `finished_at`, `ingested_at`) ahora usan `America/Mexico_City` en vez de UTC del servidor.

### Responsive / Mobile
- CSS `@media` para navegación scrollable, métricas en wrap, header compacto.
- Tooltips ocultos en móvil.

## Migración desde 5.6.7

```bash
cd ~/ReportesBESS
git fetch --tags
git checkout -f v5.7.0
docker compose up -d --build
```

## Archivos nuevos

- `bess/ui/generacion_tab.py`

## Versión anterior

- **5.6.7** — Fix barras de progreso visibles en sync y reportes.
