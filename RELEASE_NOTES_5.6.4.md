# BESS 5.6.4

## Resumen

Rol **superadmin** con Mantenimiento DB integrado en la app principal, herramientas SQLite, preflight de reloj en el cron y ajuste del PDF acumulado (Día Tipo sin fecha).

## Cambios principales

### Rol superadmin y Mantenimiento DB
- Nuevo rol `superadmin`: permisos de administrador + sección **Mantenimiento DB** en el sidebar.
- Integración de `bess/ui/db_tools/` en el reporteador (Resumen, importar/exportar CSV, purgar, migrar, vaciar).
- App aislada `streamlit_db_tools.py` (puerto 8502) restringida a superadmin.
- Ejemplo de usuario en `deploy/secrets.toml.example` y `.streamlit/secrets.toml.example`.

### Preflight reloj (cron)
- `scripts/preflight_reloj.py`: verifica zona `America/Mexico_City` y NTP antes del sync automático.
- `scripts/cron_sincronizar.sh`: omite sync si falla el preflight; escribe `data/sync_preflight.json`.
- `bess/data/sync_preflight.py` + aviso en sidebar admin cuando hay advertencias.

### PDF acumulado
- `bess/reports/accumulated_pdf.py`: gráfica Día Tipo sin fecha en el título (solo kWh arriba de la gráfica).

## Migración desde 5.6.3

```bash
cd ~/ReportesBESS
git fetch --tags
git checkout v5.6.4
docker compose up -d --build
```

Agregar superadmin en `deploy/secrets.toml` (no va en git):

```toml
[users.superadmin]
password = "CAMBIAR"
rol = "superadmin"
nombre = "Superadministrador"
```

```bash
docker compose restart bess
```

Comprobar: login como superadmin → sidebar **Mantenimiento DB** → herramientas SQLite.

## Versión anterior

- **5.6.3** — Fix cogeneración en sync automático y cron Docker robusto.
