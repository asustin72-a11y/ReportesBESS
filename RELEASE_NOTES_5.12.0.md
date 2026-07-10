# BESS 5.12.0

## Resumen

Nueva sección **Emisiones CO₂** (a la derecha de Recibo): huella Scope 2 mensual Con BESS vs Sin BESS, comparación de generación local (cogeneración / granja solar) frente a red, y PDF descargable.

## Cambios principales

### Sección Emisiones
- Navegación: pestaña **Emisiones** junto a Recibo.
- Factores de red **Marcado**: Base 0.30 / Intermedio 0.45 / Punta 0.65 kg CO₂/kWh.
- KPIs Con/Sin BESS con ahorro en t y %.
- Tablas y gráficas por periodo; títulos y leyendas centrados.

### Generación local
- **IUSA 1 (cogeneración):** emisiones locales con escenario plano EF = 0.45 kg CO₂/kWh vs emisiones de red Marcado si esos kWh vinieran de la red; beneficio neto en t y %.
- **IUSA 2 / Aragón (solar):** emisiones locales = 0; neto = desplazamiento de red.
- Gráfica de energía: generación como **base** apilada; consumo de red arriba (igual en Con/Sin BESS).

### PDF
- Reporte descargable con encabezado alineado (logo + título sin solapamiento).
- Subíndice tipográfico CO₂ en ReportLab.

## Archivos nuevos

- `bess/cfe/emisiones.py`
- `bess/ui/emisiones_tab.py`
- `bess/reports/emisiones_pdf.py`

## Migración desde 5.11.0

```bash
cd ~/ReportesBESS
git fetch --tags
git checkout -f v5.12.0
docker compose up -d --build
```

No requiere reprocesar el pipeline: usa `ENERGIA_*_POR_DIA.csv` y generación diaria ya existentes.

## Versión anterior

- **5.11.0** — Netmetering GDMTH, FP Q1+Q4, demanda real y sync API hasta hoy.
