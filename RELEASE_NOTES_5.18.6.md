# BESS 5.18.6 — Suite: selector completo

## Resumen

El portal **Suite IUSASOL** incluye las cinco apps: BESS, Granja, Descargas,
**Análisis de Perfil** y **Consultar Tarifa**. Versión **v5.18.6** visible en
el encabezado del selector.

## Cambios

- `suite/`: módulos `analisis_perfil` y `consultar_tarifa` en el selector
- `analisis_perfil` / `tarifas_cfe`: soporte `desde_suite=True` (misma sesión)
- Imagen Compose: `bess:5.18.6`

## Migración desde 5.18.5

```bash
cd ~/ReportesBESS
git fetch --tags
git checkout -f v5.18.6
docker compose up -d --build
```
