# BESS 5.8.0

## Resumen

Nueva subestación IUSA_ARAGON, catálogo/tarifas/usuarios en SQLite (superadmin), generación en perfil de carga y PDF, sidebar oculta para visualizadores, y autorefresh cada 15 min.

## Cambios principales

### Subestación IUSA_ARAGON
- Alta en catálogo (`Subestaciones.csv`, `Medidores.csv`) con medidores API CS1980, CS1991 y CYM773.
- Sync automático por número de serie sin alias manual.
- Pipeline completo: sync → verificar → filtrar → reportes.

### Generación en perfil de carga
- Curva de generación en perfil horario para **todas** las subestaciones con recurso (granja, cogeneración, individual).
- Misma lógica en vista previa y PDF diario.

### PDF diario — toggle generación
- Checkbox en pestaña Reportes: *"Incluir generación en el perfil del PDF"*.
- Vista previa y PDF alineados (`incluir_generacion`).

### Catálogo en SQLite (superadmin)
- Tablas: `catalog_subestaciones`, `catalog_tipo_medidor`, `catalog_medidores`.
- UI admin con tabs CRUD y validación de medidores.
- `cargar_catalogo()` lee desde BD; CSV solo migra si las tablas están vacías.
- Expander **Catálogo** en sidebar superadmin.

### Tarifas en SQLite (superadmin)
- Tabla `catalog_tarifas` (`tarifa`, `mes`, `valor`).
- Tab **Tarifas** en admin catálogo (CRUD).
- Admin (`admin`): sidebar **Tarifas** sigue en solo lectura (mes actual).

### Usuarios en SQLite (superadmin)
- Tabla `catalog_usuarios` (`username`, `password_hash`, `rol`, `nombre`, `activo`).
- Tab **Usuarios** en admin catálogo.
- `get_usuarios()` lee BD (activos); bootstrap desde `secrets.toml` / `BESS_USERS` si vacío.
- Reglas: mínimo 1 superadmin activo, no auto-eliminación, contraseña obligatoria en altas.

### UX — rol visualizador (`user`)
- Barra lateral **oculta por completo** (CSS + script persistente).
- Sin contenido ni controles de expansión en sidebar.

### Autorefresh
- Recarga automática de la app cada 15 minutos (`streamlit-autorefresh`).

## Migración desde 5.7.0

```bash
cd ~/ReportesBESS
git fetch --tags
git checkout -f v5.8.0
docker compose up -d --build
```

En el primer arranque, el catálogo CSV y tarifas/usuarios de `secrets.toml` se migran a SQLite si las tablas están vacías.

## Archivos nuevos

- `bess/data/catalog_db.py`
- `bess/data/tariffs_db.py`
- `bess/data/users_db.py`
- `bess/tariffs/store.py`
- `bess/ui/catalog_admin/` (page, service, users_store)

## Versión anterior

- **5.7.0** — Sección Generación, logout limpio, rediseño Mantenimiento BD, timezone MX.
