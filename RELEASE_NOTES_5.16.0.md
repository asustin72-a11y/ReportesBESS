# BESS 5.16.0

## Resumen

El importador CSV a SQLite **ya no omite** el primer registro del día cuando no
es `00:05`. Se guardan todas las filas del archivo (p. ej. slots `00:00` de
BESS/ISOL). Ese filtro tenía sentido en el flujo tipo hojas Excel; con SQLite
y el pipeline actual solo perdía datos reales.

## Cambios principales

### Import CSV sin filtro de primer intervalo

- Eliminado `filtrar_primer_registro_dia` y el parámetro/flag `--sin-filtro-dia`.
- UI Mantenimiento DB: sin checkbox de filtro `00:05`.
- Scripts `importar_bess_iusa2` / `importar_ion_iusa2` y fallback pcarga alineados.
- Test de regresión: conserva `00:00` + `00:05` en el mismo día.
- Documentación (guía admin / ION) actualizada.

## Migración desde 5.15.0

No cambia esquema de BD ni estructura de CSV. Tras el deploy, si un medidor
perdió filas `00:00` en un import anterior, **vuelva a importar** el mismo CSV
para recuperarlas (upsert).

Antes de `git checkout -f` en el servidor, respalde `data/` como en 5.15.0:

```bash
cd ~/ReportesBESS
ts=$(date +%Y%m%d-%H%M%S)
tar czf ~/bess-data-backup-$ts.tgz \
  data/ArchivosProcesados \
  data/ArchivosReporte \
  data/ArchivosFuente \
  data/bess_perfiles.db

git fetch --tags
git checkout -f v5.16.0
sed -i 's/\r$//' scripts/cron_sincronizar.sh deploy/install-cron.sh
tar xzf ~/bess-data-backup-$ts.tgz
docker compose up -d --build
```

## Versión anterior

- **5.15.0** — Soft-fail API y fallback pcarga IUSA 1/2.
