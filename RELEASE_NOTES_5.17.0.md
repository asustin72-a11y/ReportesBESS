# BESS 5.17.0 — Suite IUSASOL (BESS + Granja)

## Resumen

Portal único **Suite IUSASOL**: un login y selector **BESS | Granja Solar**.
Integra el reporteador Granja (21 MEGAs, energía/ingresos DIST, PDF diario y
mensual) en el mismo contenedor y la misma SQLite que BESS.

## Cambios principales

### Suite

- `streamlit_app.py` arranca el portal (`suite/`).
- Tras autenticarse: elegir módulo BESS o Granja; **← Suite** para volver.
- Entradas directas: `streamlit_bess.py`, `streamlit_granja.py`.

### Granja Solar

- Paquete `granja/`: sync API Farm → SQLite, dashboard, reportes PDF.
- Tarifas históricas DIST (`catalog_tarifas_hist` + `tarifa_por_fecha`).
- Sidebar de sync solo para **superadmin**; resto a pantalla completa.
- Autorefresh de vista cada 15 min (sin bloquear con sync en la UI).
- Cron Linux: `deploy/install-cron-granja.sh` + `scripts/cron_sincronizar_granja.sh`.
- CLI: `python scripts/sincronizar_granja_megas.py --quiet`.
- Rendimiento: MIN/MAX de fechas (sin DISTINCT masivo), precios vectorizados,
  caché de resumen (~2 min).

### Docs / Docker

- `docs/DOCKER.md` y README actualizados (Suite + ambos crons).
- Imagen Compose: `bess:5.17.0`.

## Migración desde 5.16.1

1. Desplegar el tag (rebuild Docker).
2. Instalar cron Granja si aún no está:
   ```bash
   bash deploy/install-cron-granja.sh
   ```
3. Si el servidor **no** tiene perfiles MEGA en SQLite, sincronizar una vez
   (sidebar superadmin o CLI) o copiar `perfil_carga` / `catalog_tarifas_hist`
   desde un entorno que ya los tenga.
4. La sync BESS (`install-cron.sh`) sigue igual; no la reemplaza el cron Granja.

```bash
cd ~/ReportesBESS
ts=$(date +%Y%m%d-%H%M%S)
echo 'TU_PASSWORD' | sudo -S tar czf ~/bess-data-backup-$ts.tgz \
  data/ArchivosProcesados data/ArchivosReporte data/ArchivosFuente data/bess_perfiles.db
echo 'TU_PASSWORD' | sudo -S chown bess:bess ~/bess-data-backup-$ts.tgz

git fetch --tags
git checkout -f v5.17.0
sed -i 's/\r$//' scripts/cron_sincronizar.sh scripts/cron_sincronizar_granja.sh \
  deploy/install-cron.sh deploy/install-cron-granja.sh || true

echo 'TU_PASSWORD' | sudo -S tar xzf ~/bess-data-backup-$ts.tgz -C ~/ReportesBESS
docker compose up -d --build
bash deploy/install-cron-granja.sh
grep __version__ bess/__init__.py
```

Abrir `http://IP:8501` → login → **BESS** o **Granja Solar**.

## Versión anterior

- [5.16.1](RELEASE_NOTES_5.16.1.md) — totales kWh: sumar y luego redondear
