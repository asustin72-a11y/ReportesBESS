# BESS 5.6.1

## Resumen

Flujo unificado IUSA 1 + IUSA 2, participación Shapley de capacidad CFE, generación acumulada, mejoras de UI/sesión y despliegue Docker.

## Cambios principales

### Flujo unificado por subestación
- **IUSA 1:** cogeneración (medidor tipo 5, API `cogeneracion` / CS1305) integrada al pipeline de verificar → filtrar → reportes.
- **IUSA 2:** granja solar (tipo 4) sin cambios de comportamiento.
- Reportes `ENERGIA_Generacion_{Sub}_POR_DIA.csv` para ambas subestaciones.

### Participación Capacidad (Shapley)
- Nueva pestaña **Participación Capacidad** con escenarios D0–Dcb y criterio CFE.
- Módulo `bess/cfe/shapley.py`.
- IUSA 1: cogeneración (`KWH_ENT`); IUSA 2: granja (`KWH_REC`).

### UI y reportes
- Fila **Generación Acumulada** en tabla de energía y PDF diario (IUSA 1 e IUSA 2).
- Logout con recarga limpia (sin restos de sidebar).
- Sidebar colapsada (usuario) / expandida (admin) al entrar.

### Pipeline y datos
- Demanda rodante mensual: 00:05 y 00:10 = 0; primer valor a 00:15.
- Catálogo: `Tipo_Medidor` tipo 5 Cogeneración; `Medidores.csv` con `Cogeneracion`.

### Docker y operación
- `Dockerfile`, `docker-compose.yml`, `docs/DOCKER.md`.
- Cron horario: `scripts/cron_sincronizar.sh`, `deploy/install-cron.sh`.
- Script de despliegue UI: `deploy/actualizar-ui-vm.ps1`.

## Migración desde 5.6.0

1. Actualizar `data/Tarifas/Medidores.csv` y `Tipo_Medidor.csv` (tipo 5 Cogeneración).
2. Sincronizar medidor **Cogeneracion** (API) en IUSA 1.
3. Ejecutar pipeline: **Sincronizar** → **Verificar** → **Filtrar** → **Generar reportes**.
4. En Docker: `docker compose up -d --build`.

## Versión anterior

- **5.6.0** — Catálogo CSV, rutas por subestación, pipeline modular.
