# BESS 5.6.7

## Resumen

Hotfix de barras de progreso en sync manual y generación de reportes.

## Cambios principales

### UI — barras de progreso visibles
- Corregido `SyntaxError` en `bess/ui/pipeline_progress.py`.
- Lectura de stderr en el hilo principal (Streamlit no actualiza widgets desde hilos secundarios).
- Placeholder de progreso **fuera** del expander colapsado en la sidebar.
- Evento inicial `0/6` al arrancar `sincronizar_perfiles.py --ui-progress`.

## Migración desde 5.6.6

```bash
cd ~/ReportesBESS
git fetch --tags
git checkout -f v5.6.7
docker compose up -d --build
```

## Versión anterior

- **5.6.6** — Cursor CSV `Ultima_Sincronizacion.csv` y barras de progreso (con bug de visibilidad).
