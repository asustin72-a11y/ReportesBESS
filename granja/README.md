# Granja Solar IUSASOL

Módulo de la suite de reporteadores IUSASOL (hermano de BESS).

## Alcance V1

- Integrado en la **Suite IUSASOL** (`streamlit_app.py`: login → BESS | Granja)
- Entrada directa: `streamlit run streamlit_granja.py`
- 21 MEGAs (Mega01–Mega21 / CS0493)
- Perfil de carga **API Farm** (`Reports/Farm`) a **5 minutos**; canal 0 → `KWH_REC` (sin escala)
- Ingresos con tarifa **DIST** (Base / Intermedio / Punta), con soporte histórico año-mes
- **Todo en SQLite** (`data/bess_perfiles.db`): sync, agregados, tarifas, catálogo y auth
- **Sin generar CSV** de perfiles ni reportes
- Auth y catálogo reutilizados de BESS
- Dashboard día/mes + PDF diario / mensual
- **Sin** monitoreo en vivo, demanda, recibo CFE, clima ni factor de planta
- **Operación objetivo:** servidor **Linux** (Docker + cron, ver `docs/DOCKER.md`)

Fecha de inicio de sync: **2026-01-01**. Capacidad de referencia: **22 MW**.

## Ejecución (desarrollo local)

```bash
pip install -r requirements.txt
streamlit run streamlit_granja.py
```

Credenciales: las mismas que BESS (tabla `catalog_usuarios` / secrets).

## Sync automática cada 15 min

La fuente de verdad en producción es el **cron Linux** (igual que BESS). El
autorefresh de Streamlit también dispara sync incremental si la app está abierta
(con lock para no solaparse con el cron ni con el botón manual).

### Servidor Linux (producción)

```bash
bash deploy/install-cron-granja.sh
```

Prueba manual:

```bash
bash scripts/cron_sincronizar_granja.sh
tail -f logs/granja-sync-$(date +%Y%m%d).log
```

Por defecto usa Docker (`bess-app` / servicio `bess`, mismo volumen `data/` y
secrets). Para forzar Python en el host:

```bash
GRANJA_SYNC_HOST=1 bash scripts/cron_sincronizar_granja.sh
```

### Desarrollo Windows (opcional)

```powershell
powershell -ExecutionPolicy Bypass -File scripts\cron_sincronizar_granja.ps1
```

### CLI

```bash
python scripts/sincronizar_granja_megas.py --quiet
```

Logs: `logs/granja-sync-YYYYMMDD.log`.

## Estructura

```
granja/
  config/     # constantes y lista de MEGAs
  data/       # sync API + agregados DIST
  reports/    # PDF diario / mensual
  ui/         # Streamlit
streamlit_granja.py
scripts/cron_sincronizar_granja.sh
deploy/install-cron-granja.sh
```
