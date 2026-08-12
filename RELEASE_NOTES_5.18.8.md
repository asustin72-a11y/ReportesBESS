# BESS 5.18.8 — Generación múltiple, Shapley N y catálogo

## Resumen

IUSA 1 (y cualquier subestación con `Generacion=2`) admite **varios medidores
tipo 5** (p. ej. cogeneración + solar). La **Participación Shapley** atribuye
capacidad CFE a **cada generador + BESS**. Incluye fix del cursor COMBINADO
(aviso de desfase) y el **manual PDF de alta de medidores/subestaciones**.

## Cambios

### Catálogo y pipeline
- `Generacion=2`: uno o más tipo 5 (ya no solo uno)
- Pipeline: filtrar / reportes / rebuild / desfase por cada recurso de generación
- Diario `ENERGIA_Generacion_{sub}_POR_DIA.csv` sumado desde todos los individuales
- UI Generación: selector Total / medidor

### Shapley (Participación capacidad)
- N jugadores = cada fuente de generación + BESS (3 en IUSA 1 con cogen + solar)
- 2^n coaliciones; UI con tarjeta por participante
- PDF acumulado sigue usando la parte BESS

### Emisiones y perfil
- Cogener* → gas; resto tipo 5 → solar
- Perfil / COMBINADO de generación por medidor

### Correctivos
- Cursor COMBINADO: parseo de `FECHA_HORA` por índice de cabecera (menos falsos avisos de desfase)

### Documentación
- `docs/MANUAL_CATALOGO.md` · PDF — reglas y pasos de alta
- Manual Suite y generadores PDF actualizados en el índice

## Tras el deploy (operación)

1. Dar de alta el medidor solar (tipo 5) en Catálogo si aún no está.
2. **Validar → Guardar → Sincronizar → Verificar → Filtrar → Generar reportes**.
3. Revisar Generación y Participación (3 tarjetas cuando haya 2 tipo 5 + BESS).

## Migración desde 5.18.7

```bash
cd ~/ReportesBESS
# Respaldo de data/ según GUIA_ADMINISTRADOR antes del checkout -f
git fetch --tags
git checkout -f v5.18.8
docker compose up -d --build
```

## Respaldo local

```powershell
.\scripts\crear_respaldo.ps1
```

Salida: `backups\BESS_v5.18.8_respaldo_YYYY-MM-DD.zip` — ver `RESTAURACION_LOCAL.md`.
