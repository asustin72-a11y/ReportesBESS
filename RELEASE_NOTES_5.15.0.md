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

## Archivos nuevos

- `bess/data/ingest/pcarga/fallback.py`
- `tests/test_pcarga_fallback.py`
- `tests/test_pcarga_auto_fallback.py`
- `tests/test_sync_api_soft_fail.py`

## Migración desde 5.14.0

```bash
cd ~/ReportesBESS
git fetch --tags
git checkout -f v5.15.0
sed -i 's/\r$//' scripts/cron_sincronizar.sh deploy/install-cron.sh
docker compose up -d --build
```

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
