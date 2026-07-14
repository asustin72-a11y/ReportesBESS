# BESS 5.6.6

## Resumen

Cursor de sincronización por medidor (`Ultima_Sincronizacion.csv`), barras de progreso en sync/reportes manuales y script de inicialización.

## Cambios principales

### CSV Ultima_Sincronizacion.csv
- `data/Tarifas/Ultima_Sincronizacion.csv`: última fecha por `medidor_id`; base para la siguiente petición de perfiles.
- Si se edita la fecha a un valor anterior, el sync redescarga desde ahí y sobrescribe registros en SQLite.
- Tras sync exitoso, el CSV se actualiza con `MAX(fecha)` en BD.
- `bess/data/sync_cursor.py`, integración en API, ION Modbus y granja IUSA 2.
- `scripts/inicializar_ultima_sincronizacion.py`: crea el CSV desde la BD.
- `scripts/purgar_api_desde.py`: actualiza el CSV al purgar.

### UI — barras de progreso
- Sync manual y **Generar reportes**: barra con pasos (Modbus, API, export, validación, combinados, etc.).
- `bess/ui/pipeline_progress.py`, flag `--ui-progress` en `sincronizar_perfiles.py`.

## Migración desde 5.6.5

```bash
cd ~/ReportesBESS
git fetch --tags
git checkout v5.6.6
docker compose up -d --build
```

Inicializar cursor (si aún no existe el CSV):

```bash
docker compose exec -T bess python scripts/inicializar_ultima_sincronizacion.py
sudo chown bess:bess data/Tarifas/Ultima_Sincronizacion.csv
```

Editar fechas por medidor antes del sync manual:

```bash
nano data/Tarifas/Ultima_Sincronizacion.csv
```

Solo granja IUSA 2 desde una fecha:

```bash
docker compose exec -T bess python scripts/purgar_api_desde.py \
  --medidor Generacion_IUSA_2 --desde "2026-06-27 23:55:00" --ejecutar
docker compose exec -T bess python scripts/sincronizar_granja_iusa2.py \
  --desde 2026-06-27 --export
```

Reactivar cron (cuando el reloj y los perfiles estén validados):

```bash
bash deploy/install-cron.sh
```

## Versión anterior

- **5.6.5** — Fix cron con `bash` explícito y preflight reloj menos estricto.
