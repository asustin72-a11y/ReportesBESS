# BESS 5.18.5 — Suite IUSASOL

## Resumen

Mejora de presentación en las tablas del **Reporteador de Granja**:
separadores de miles, signo `$` en ingresos y unidades en los encabezados.

## Cambios

- `granja/ui/pages.py`: formateo de tablas (kWh con miles, ingresos con `$`);
  columnas renombradas con unidades; se oculta `medidor_id`; `etiqueta` se
  muestra como **Medidor**. Las gráficas siguen usando valores numéricos.
- Imagen Compose: `bess:5.18.5`.

## Migración desde 5.18.4

```bash
cd ~/ReportesBESS
git fetch --tags
git checkout -f v5.18.5
docker compose up -d --build
grep __version__ bess/__init__.py
```

No requiere regenerar datos ni cambios de sudoers.
