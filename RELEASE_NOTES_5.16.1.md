# BESS 5.16.1

## Resumen

Totales de carga/descarga BESS: **sumar primero y redondear al final**, igual en
recuadros, columna Total de la tabla, PDF diario y reporte acumulado. Evita
desfases de 1–2 kWh entre UI y tabla.

## Cambios

- Recuadros de Operación (y resumen del PDF diario) usan el mismo total que la
  tabla (`carga_total` / `descarga_total`).
- Columna **Total** de la tabla de energía: `round(Base + Intermedio + Punta)`
  sobre la suma cruda (las celdas por periodo siguen redondeadas solo para
  mostrar).
- Misma regla en `daily_pdf` y en el acumulado de ahorros.

## Migración desde 5.16.0

Solo código de presentación. **No** requiere Rebuild CSV ni tocar SQLite.

```bash
cd ~/ReportesBESS
# Respaldo data (CSV suelen ser root → sudo)
ts=$(date +%Y%m%d-%H%M%S)
echo 'TU_PASSWORD' | sudo -S tar czf ~/bess-data-backup-$ts.tgz \
  data/ArchivosProcesados data/ArchivosReporte data/ArchivosFuente data/bess_perfiles.db
echo 'TU_PASSWORD' | sudo -S chown bess:bess ~/bess-data-backup-$ts.tgz

git fetch --tags
git checkout -f v5.16.1
sed -i 's/\r$//' scripts/cron_sincronizar.sh deploy/install-cron.sh || true

echo 'TU_PASSWORD' | sudo -S tar xzf ~/bess-data-backup-$ts.tgz -C ~/ReportesBESS
docker compose up -d --build
grep __version__ bess/__init__.py
```

## Versión anterior

- **5.16.0** — Import CSV sin omitir registros.
