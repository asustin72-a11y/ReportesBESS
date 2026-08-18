# BESS 5.18.15 — Granja periodo alineado y perfil generación TOU

## Resumen

Ajusta el selector de periodo en **Granja Solar** y corrige el perfil de
generación (BESS) para que Base / Intermedio / Punta no se unan con
diagonales al cambiar de horario.

## Cambios

### Granja — Periodo de consulta
- Misma rejilla atajos (6) y fechas (`2+2+1+1`)
- Botones a la misma altura; marcador CSS sin descompensar la 1.ª columna
- Bloque «Días» alineado con los date inputs

### Generación — Perfil por periodo
- Cada serie usa toda la línea del día: kW en su horario y **0** fuera
- Elimina la diagonal Intermedio→Punta→Intermedio (y análogo en Base/Punta)

## Migración desde 5.18.14

```bash
cd ~/ReportesBESS
git fetch --tags
git checkout -f v5.18.15
docker compose up -d --build
```
