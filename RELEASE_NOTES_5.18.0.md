# BESS 5.18.0 — Suite IUSASOL

## Resumen

Release de suite con **navegación unificada**, módulo **Descargas API**
(acceso para todos los roles) y **demanda rodante con aislamiento TOU**
(reinicio por periodo tarifario, no por mes).

## Cambios principales

### Navegación de sesión (todos los módulos)

- **Volver a la Suite** y **Cerrar sesión** siempre en la **barra superior**
  (nunca en el sidebar), con el mismo texto y orden.
- Aplica a selector Suite, BESS y Granja Solar.
- Sidebar de Granja (superadmin): solo branding + sync.

### Descargas API

- Paquete `descargas/`: Clientes (ISOL), Granja (Farm) y Porteo → CSV.
- Acceso para **user / admin / superadmin** como **tercer módulo** del
  selector post-login (junto a BESS y Granja Solar).
- Standalone: `streamlit run streamlit_descargas.py`.

### Demanda rodante TOU

- `demanda_rodante_15min_por_periodo`: no mezcla subintervalos de tarifas
  distintas; tras cambio de periodo (Base/Intermedio/Punta) los 2 primeros
  intervalos de 5 min valen 0.
- Cableado en COMBINADO y Shapley capacidad.
- Tras desplegar, **regenerar reportes** (o esperar pipeline incremental)
  para recalcular demanda en combinados históricos.

### Docker / versión

- Imagen Compose: `bess:5.18.0`.

## Migración desde 5.17.0

1. Respaldo de `data/` (como en releases anteriores).
2. `git fetch --tags && git checkout -f v5.18.0`
3. `docker compose up -d --build`
4. Regenerar COMBINADO / reportes afectados por demanda TOU si aplica.

```bash
cd ~/ReportesBESS
ts=$(date +%Y%m%d-%H%M%S)
echo 'TU_PASSWORD' | sudo -S tar czf ~/bess-data-backup-$ts.tgz \
  data/ArchivosProcesados data/ArchivosReporte data/ArchivosFuente data/bess_perfiles.db
echo 'TU_PASSWORD' | sudo -S chown bess:bess ~/bess-data-backup-$ts.tgz

git fetch --tags
git checkout -f v5.18.0
sed -i 's/\r$//' scripts/cron_sincronizar.sh scripts/cron_sincronizar_granja.sh \
  deploy/install-cron.sh deploy/install-cron-granja.sh || true

echo 'TU_PASSWORD' | sudo -S tar xzf ~/bess-data-backup-$ts.tgz -C ~/ReportesBESS
docker compose up -d --build
grep __version__ bess/__init__.py
```

Abrir `http://IP:8501` → login → **BESS**, **Granja Solar** o **Descargas API**.
En cada módulo: barra superior → **Volver a la Suite** / **Cerrar sesión**.

## Pruebas

- `tests/test_demand_periodo.py`
- `tests/test_combined_incremental.py` (contrato frontera TOU)

## Versión anterior

- [5.17.0](RELEASE_NOTES_5.17.0.md) — Suite IUSASOL (BESS + Granja Solar)
