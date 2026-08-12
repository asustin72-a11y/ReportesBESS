# BESS 5.18.10 — Rebuild total de reportes desde BD

## Resumen

Nuevo botón en **Mantenimiento DB → Rebuild CSV** para rehacer **todos** los
archivos de reporte a partir de SQLite (útil tras integrar medidores de
generación con histórico desde mayo).

## Cambios

- **Rebuild total desde BD:** reexporta todos los medidores exportables,
  borra CSV de ArchivosProcesados / ArchivosReporte / ReportesDiarios y ejecuta
  Verificar → Filtrar → Generar reportes. SQLite no se modifica.
- Mejor soporte de rebuild del agregado granja `Generacion_IUSA_2`.

## Uso

1. Superadmin → **Mantenimiento DB** → **Rebuild CSV**
2. Sección *Rebuild total desde la base de datos*
3. Fecha desde (p. ej. `2026-05-01`) → confirmar → **Rehacer todos los reportes desde BD**

Puede tardar varios minutos.

## Migración desde 5.18.9

```bash
cd ~/ReportesBESS
git fetch --tags
git checkout -f v5.18.10
docker compose up -d --build
```
