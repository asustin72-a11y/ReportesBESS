# BESS 5.6.2

## Resumen

Nueva sección **Reportes** con reporte acumulado mensual (ahorros BESS), gráfica **Día Tipo** dinámica, participación Shapley mejorada en UI y sync automático cada 15 minutos en Docker.

## Cambios principales

### Reporte acumulado
- Sección **Reportes** con pestañas *Reporte diario* y *Reporte acumulado*.
- Ahorros del mes a la fecha de corte: carga/descarga, eficiencia, arbitraje y atribución Shapley solo del BESS (kW y MXN).
- PDF acumulado: gráfica Día Tipo arriba y recuadros de métricas abajo.
- Módulos `bess/reports/accumulated.py`, `accumulated_pdf.py`, `bess/ui/reportes_tab.py`.

### Día Tipo
- Gráfica generada en tiempo real (sin imagen estática).
- Se elige el último martes, miércoles o jueves **anterior** a la fecha de corte con carga y descarga BESS (puede ser de otro mes).
- Título: `Día Tipo · {Subestación} · {Medidor facturación}`.
- Módulo `bess/reports/dia_tipo.py`.

### Participación Capacidad y UI
- Tabla Shapley con formato mejorado y tarjetas destacadas de ahorro en demanda (kW + MXN).
- Filas de demanda resaltadas en el resumen acumulado.
- Eliminado panel **Mantenimiento (Fase 7)** de la sidebar admin (el script CLI sigue disponible).

### Operación Docker
- Cron de sincronización: de horario a **cada 15 minutos** (`deploy/install-cron.sh`, `scripts/cron_sincronizar.sh`).
- Documentación actualizada en `docs/DOCKER.md`.

## Migración desde 5.6.1

1. `git pull` y `docker compose up -d --build` (o `deploy/actualizar-ui-vm.ps1` en la VM).
2. En servidores con cron ya instalado: volver a ejecutar `bash deploy/install-cron.sh` para aplicar el intervalo de 15 min.
3. Generar reportes CSV si faltan datos del mes en curso (**Generar reportes** o pipeline completo).

## Versión anterior

- **5.6.1** — Flujo unificado IUSA 1 + IUSA 2, Shapley capacidad, generación acumulada, Docker.
