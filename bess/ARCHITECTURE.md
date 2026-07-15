# Arquitectura BESS — refactor web

Documento de referencia para la migración de monolito (exe) a paquete modular (web).

Ver también [`PLAN_MIGRACION_SQLITE.md`](PLAN_MIGRACION_SQLITE.md): la segunda migración en curso, de CSV a SQLite en cada etapa del pipeline (no solo en la ingesta).

## Situación actual

| Archivo | Líneas | Rol |
|---------|--------|-----|
| `bess_core.py` | ~90 | Fachada de compatibilidad (re-exporta `bess.*`) |
| `streamlit_app.py` | 21 | Entrada Streamlit Cloud |
| `legacy/app_plotly.py` | 4168 | **Legacy archivado** (monolito pre-refactor, no usado ni importado) |
| `legacy/styles.py` | 549 | **Legacy archivado** (no usado) |

**Problemas:** duplicación de rutas/números/tarifas, lógica de negocio mezclada con UI, imports lazy difíciles de testear.

## Estructura objetivo

```
bess/
├── config/          # Rutas, constantes, tema          [Fase 1 ✓]
├── core/            # Números, kVArh, fechas, consola     [Fase 1 ✓]
├── cfe/             # Periodos, costos, arbitraje              [Fase 4 ✓]
├── tariffs/         # Carga Tarifas_2026.csv                   [loader ✓]
├── data/            # ETL: verify, filter, aggregates          [Fase 5 ✓]
├── reports/         # PDF diario (ReportLab)                   [Fase 6 ✓]
├── cfe/receipt/     # Recibo simulado HTML/PDF                 [Fase 7 ✓]
├── charts/          # Figuras Plotly (sin Streamlit)           [Fase 8 ✓]
└── ui/              # Streamlit: auth, CSS, sidebar, pages     [Fase 9 ✓]
```

Raíz del repo (compatibilidad):

- `streamlit_app.py` → `bess.ui.app.main()` ✓
- `legacy/app_plotly.py` → monolito pre-refactor archivado; no se importa desde ningún módulo activo

## Fases de migración

| Fase | Módulo | Estado |
|------|--------|--------|
| 1 | `config/`, `core/numbers`, `core/kvarh` | **Hecho** |
| 2 | `tariffs/` — unificar `cargar_tarifas` | **Hecho** (loader; edición UI pendiente en app) |
| 3 | `cfe/periods.py` — temporada, festivo, periodo horario | **Hecho** |
| 4 | `cfe/` — costos, arbitraje, capacidad, factor potencia | **Hecho** (costos/arbitraje; capacidad/FP en app) |
| 5 | `data/` — split de `bess_core` (verify, filter, reportes CSV) | **Hecho** |
| 6 | `reports/daily_pdf.py` | **Hecho** |
| 7 | `cfe/receipt/` — recibo simulado HTML/PDF | **Hecho** |
| 8 | `charts/` — Plotly; archivar `styles.py` | **Hecho** |
| 9 | `ui/` — tabs, sidebar, auth | **Hecho** (tabs en `ui/pages.py`; gráficas en `charts/`) |
| 10 | Credenciales → variables de entorno | **Hecho** |

## Reglas

1. **`bess/*` no importa `streamlit`** (excepto `bess/ui/`).
2. **`bess/data/` no importa `bess/ui/`**.
3. Duplicar código solo durante transición; eliminar de `app_plotly.py` / `bess_core.py` al mover.
4. Tests unitarios sobre `bess/core`, `bess/cfe`, `bess/tariffs` sin levantar la app -- iniciado en `tests/` (`pytest`): numbers, kvarh, periods, power_factor, tariffs/loader, verify (incremental). Falta cubrir shapley, arbitrage y el resto de `cfe/`.

## Qué permanece en `bess_core.py`

Fachada de ~90 líneas: re-exporta `bess.data`, `bess.cfe`, `bess.tariffs` y `bess.reports` para compatibilidad con `app_plotly.py`. Sin lógica propia.

Capacidad y factor de potencia están en `bess/cfe/capacity.py` y `bess/cfe/power_factor.py`.
Gráficas Plotly en `bess/charts/`; pestañas Streamlit en `bess/ui/pages.py`.

## Autenticación (Fase 10)

Usuarios en `bess/config/users.py` (parseo/validación). La app los carga desde:

1. **`.streamlit/secrets.toml`** — sección `[users.<login>]` (recomendado en Streamlit Cloud)
2. **`BESS_USERS`** — JSON en variable de entorno o en secrets

Plantillas: `.streamlit/secrets.toml.example`, `.env.example`. Contraseñas en texto se hashean (SHA-256) al cargar; también se acepta `password_hash`.

## Qué sale de `app_plotly.py`

- Cálculos CFE → `bess/cfe/`
- Tarifas CSV → `bess/tariffs/`
- Recibo (~700 líneas) → `bess/cfe/receipt/`
-