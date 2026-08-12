# BESS 5.18.12 — Generacion=1 admite tipo 5

## Resumen

En subestaciones con **`Generacion=1` (grupo)** se pueden dar de alta medidores
**tipo 5** además de los tipo 4 del grupo (p. ej. IUSA 2: Megas + generación
individual). El pipeline y Shapley ya sumaban granja + tipo 5; solo faltaba
permitirlo en la validación del catálogo.

## Cambios

- Catálogo: `Generacion=1` requiere tipo 4 con `Grupo_Generacion`; **tipo 5 opcional**
- Textos de ayuda del admin de catálogo y `docs/MANUAL_CATALOGO.md`
- Test: IUSA_2 con Mega + tipo 5 valida OK
- Login: `strip()` de usuario/contraseña (espacios al pegar)

## Tras el deploy

1. Catálogo → alta del tipo 5 en la subestación con `Generacion=1`
2. Validar → Guardar → Sincronizar → Verificar → Filtrar → Generar reportes
3. Revisar Generación / Participación (granja + individual + BESS)

## Migración desde 5.18.11

```bash
cd ~/ReportesBESS
git fetch --tags
git checkout -f v5.18.12
docker compose up -d --build
```
