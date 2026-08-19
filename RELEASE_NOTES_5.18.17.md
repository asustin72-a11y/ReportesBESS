# BESS 5.18.17 — Análisis de Perfil: wizard + sidebar limpia

## Resumen

Corrige el crash del wizard (`analisis_paso` tras el radio) y elimina
residuos de la guía BESS en la barra lateral al contraerse.

## Cambios

- Navegación del wizard vía `_analisis_paso_goto` (antes de instanciar el radio)
- Limpieza JS/CSS de `.sidebar-guia` / tooltips BESS en Análisis de Perfil

## Migración desde 5.18.16

```bash
cd ~/ReportesBESS
git fetch --tags
git checkout -f v5.18.17
docker compose up -d --build
```
