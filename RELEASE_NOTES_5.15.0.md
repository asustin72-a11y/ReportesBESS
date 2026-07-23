# BESS 5.15.0

## Resumen

Resiliencia ante caída de `api.iusasol.mx`: el sync **no aborta** (exporta ION/BD), hay **fallback pcarga IUSA 1/2** (botón en Mantenimiento DB) y **fallback automático opt-in**. Pcarga en Docker vía SSH al host (Wine/MLE). Mensajes de sync más claros en la sidebar.

## Cambios principales

### Soft-fail API / granja

- Si falla ISOL o Farm, el sync continúa y **exporta** lo ya guardado (ION Modbus + BD).
- Validación marca solo medidores OK; no invalida el lote completo.
- Sidebar: warning de sync parcial + acción sugerida.

### Fallback pcarga IUSA 1/2

Medidores: `Banco_1`, `BESS_NORTE`, `Cogeneracion`, `BESS_SUR` (sin Aragón ni granja).

- **Manual:** Mantenimiento DB → PCarga → *Ejecutar fallback pcarga IUSA 1/2* (descarga → import `fuente=csv` → Rebuild opcional).
- **Automático (opt-in, default OFF):** tras fallo de API, el sync importa por Ethernet y luego `exportar_todos`.

```toml
[pcarga]
auto_fallback = true
# Docker: script, mle_dir, ssh_host, ssh_user, ssh_password
```

También: `PCARGA_AUTO_FALLBACK=1`, `--fallback-pcarga` / `--sin-fallback-pcarga`.

### Pcarga: SSH + rango fecha/hora

- Contenedor → host por SSH/SFTP (`paramiko`).
- UI: rango con fecha + hora (pasos de 5 min).

### Mensajes y diagnóstico

- Clasificación API/ION/granja en sidebar; aviso distinto si corrió fallback auto.
- `diagnosticar_conectividad_sync.py` actualizado (soft-fail + playbook).

### Datos CSV fuera del índice git

- `data/ArchivosProcesados/**/*.csv` y `data/ArchivosReporte/**/*.csv` dejan de
  versionarse (quedan solo `.gitkeep`). El servidor conserva su `data/` operativo.
- **Antes de `git checkout -f`:** respaldar y luego restaurar (ver Migración).

## Archivos nuevos

- `bess/data/ingest/pcarga/fallback.py`
- `tests/test_pcarga_fallback.py`
- `tests/test_pcarga_auto_fallback.py`
- `tests/test_sync_api_soft_fail.py`

## Migración desde 5.14.0

**Obligatorio — respaldar datos del servidor antes del checkout.** Este release
saca del índice git los CSV de `ArchivosProcesados` y `ArchivosReporte`. Un
`git checkout -f` puede **borrar** esos archivos del working tree; hay que
restaurarlos desde el respaldo.

```bash
cd ~/ReportesBESS

# 1) Respaldo (Procesados + Reporte + Fuente + BD)
ts=$(date +%Y%m%d-%H%M%S)
tar czf ~/bess-data-backup-$ts.tgz \
  data/ArchivosProcesados \
  data/ArchivosReporte \
  data/ArchivosFuente \
  data/bess_perfiles.db

# 2) Código
git fetch --tags
git checkout -f v5.15.0   # o el commit/tag que incluya “untrack CSV”
sed -i 's/\r$//' scripts/cron_sincronizar.sh deploy/install-cron.sh

# 3) Restaurar CSV/BD del servidor (no usar copias de otra PC)
tar xzf ~/bess-data-backup-$ts.tgz

docker compose up -d --build
```

**Datos CSV:** nunca sustituya el `data/` del servidor con regeneraciones locales.
Solo cambie estructura (columnas/nombres) con un commit explícito documentado.

### Activar fallback automático en el servidor

Solo cuando SSH/Wine pcarga esté estable (hasta ~10 min/medidor):

```toml
[pcarga]
script = "/home/bess/mle/leeperfil/pcarga.py"
mle_dir = "/home/bess/mle"
ssh_host = "172.17.0.1"   # o IP LAN del host
ssh_user = "bess"
ssh_password = "…"
auto_fallback = true
```

Sin `auto_fallback`: soft-fail + botón manual (comportamiento seguro por defecto).

**No regenera histórico.** Granja Mega y Aragón siguen dependiendo de la API.

## Versión anterior

- **5.14.0** — Mantenimiento DB (pcarga, Rebuild, Reconciliar).
