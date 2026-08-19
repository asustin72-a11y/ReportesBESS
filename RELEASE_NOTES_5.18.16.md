# BESS 5.18.16 — Granja alineada, perfil TOU sin cruce, Análisis de Perfil

## Resumen

Corrige el botón **Actual** en Granja, evita el cruce en X del perfil de
generación (manteniendo ceros fuera de horario) y rediseña **Análisis de
Perfil** (sidebar propia + flujo en 3 pasos).

## Cambios

### Granja — Periodo de consulta
- Marcador CSS **fuera** de la 1.ª columna (el `element-container` de
  Streamlit ya no descompensa **Actual**)
- CSS colapsa el wrapper del marcador, no solo el `div` interno
- Atajos con botones (sin pills)

### Generación (BESS) — Perfil por periodo
- kW activo y **0** fuera del horario TOU
- Bordes verticales en el cambio de periodo (sin diagonal ni cruce en X)

### Análisis de Perfil
- Sidebar propia del módulo (ya no hereda la guía BESS al cambiar en la Suite)
- Wizard: **Preparar → Perfiles → Resultados**
- Resultados en tabs (Resumen / Gráficas / Archivos / Descargas)
- Opciones avanzadas y filtro de fechas en expanders
- Configuración más compacta (selects + un expander de ayuda)

## Migración desde 5.18.15

```bash
cd ~/ReportesBESS
git fetch --tags
git checkout -f v5.18.16
docker compose up -d --build
```
