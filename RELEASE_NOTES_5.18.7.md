# BESS 5.18.7 — Suite: UX móvil + rendimiento

## Resumen

Portal Suite más claro (tarjetas clicables), adaptación a **móviles** en toda la
suite, y aceleración de consultas al cambiar de módulo / recargar datos.

## Cambios

### Bienvenida Suite
- Hero IUSASOL, módulos en Operación / Herramientas
- Tarjeta = botón de acceso (solo título); logout centrado abajo
- Tipografía y bordes reforzados; layout apilado en pantallas angostas

### Móvil
- Barras de sesión apiladas (BESS, Granja, Descargas, Tarifas, Análisis)
- Login a ancho completo; tablas con scroll horizontal
- Controles/atajos y métricas compactas envueltos en ≤768px / ≤480px

### Rendimiento
- Cache del COMBINADO CSV (ruta + mtime, TTL 120 s)
- Aviso de reporte desfasado: solo `sync_state` + cola CSV + cache 60 s
- Catálogo MEGAs Granja: una vez por sesión
- Playwright CFE diferido hasta consultar (no al abrir el módulo)

## Migración desde 5.18.6

```bash
cd ~/ReportesBESS
git fetch --tags
git checkout -f v5.18.7
docker compose up -d --build
```

## Respaldo local

```powershell
.\scripts\crear_respaldo.ps1
```

Salida: `backups\BESS_v5.18.7_respaldo_YYYY-MM-DD.zip` — ver `RESTAURACION_LOCAL.md`.
