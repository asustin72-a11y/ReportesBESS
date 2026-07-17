# BESS 5.14.0

## Resumen

Mantenimiento DB ampliado: descarga **pcarga** por Ethernet (CSV listo para Importar, sin escribir SQLite), **Rebuild CSV** desde SQLite, **Reconciliar** BD↔Fuente, alineación de cursores y protecciones al importar. Documentación de administrador/usuario actualizada.

## Cambios principales

### Pestaña PCarga (solo descarga)

- Lee perfil por red (`pcarga.py` + Wine/MLE en Linux).
- Endpoints y Ke en `bess/config/pcarga_endpoints.py`:
  - Banco_1 CS1996 · `172.16.111.10:5` · Ke×18400
  - BESS_NORTE CS3878 · `172.16.111.10:7` · Ke×14400
  - Cogeneracion CS1305 · `172.16.138.38:5` · ya escalado
  - BESS_SUR CS3190 · `10.255.253.246:5` · Ke×7200
  - BESS_ARAGON CYM773 · `10.255.253.139:6` · ya escalado
- CSV de salida: `Fecha`, `KWH_*`, `KVARH_*` (Wh→kWh × Ke). Insertar a mano con **Importar** si hace falta.
- Config servidor: secrets `[pcarga] script` / `mle_dir` (o `PCARGA_SCRIPT` / `MLE_DIR`).

### Rebuild CSV

- Exporta desde SQLite y regenera CSV derivados (procesado/filtrado/reportes) sin degradar la BD.
- Pestaña **Rebuild CSV** en Mantenimiento DB.

### Reconciliar y cursores

- Compara energía diaria SQLite vs ArchivosFuente.
- Evalúa/alinea `sync_state` ↔ `Ultima_Sincronizacion.csv`.
- Import CSV: alinea cursor; protege filas `fuente=csv` con energía real frente a sync API en cero.

### Documentación

- Guías admin/usuario e índice actualizados (flujo superadmin completo).

## Archivos nuevos

- `bess/config/pcarga_endpoints.py`
- `bess/data/ingest/pcarga/`
- `bess/data/csv_rebuild.py`
- `bess/data/reconcile_csv.py`
- `tests/test_pcarga_descarga.py`
- `tests/test_csv_rebuild.py`
- `tests/test_reconcile_csv.py`
- `tests/test_import_csv_cursor_y_proteccion.py`
- `tests/test_sync_log_y_cursores.py`

## Migración desde 5.13.0

```bash
cd ~/ReportesBESS
git fetch --tags
git checkout -f v5.14.0
# scripts de cron: asegurar LF
sed -i 's/\r$//' scripts/cron_sincronizar.sh deploy/install-cron.sh
docker compose up -d --build
```

### PCarga en el servidor

1. `pcarga.py` (y deps) en p.ej. `~/mle/leeperfil/` (Wine + `~/mle` ya operativos).
2. En secrets del contenedor / `.streamlit/secrets.toml`:

```toml
[pcarga]
script = "/home/bess/mle/leeperfil/pcarga.py"
mle_dir = "/home/bess/mle"
```

Si el contenedor no ve el host: montar o copiar rutas equivalentes, o ejecutar pcarga en el host y usar Importar.

**No hace falta regenerar todo el histórico.** Sync + procesar (cron) mantiene la ventana abierta.

## Versión anterior

- **5.13.0** — Confiabilidad de datos, aviso de reportes desactualizados, escritura atómica.
