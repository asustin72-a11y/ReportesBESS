# BESS 5.18.9 — Fix NameError perfil (recurso_generacion)

## Resumen

Hotfix: el dashboard fallaba al graficar el perfil porque faltaba importar
`recurso_generacion_subestacion` en `bess/charts/profile.py`.

## Migración desde 5.18.8

```bash
cd ~/ReportesBESS
git fetch --tags
git checkout -f v5.18.9
docker compose up -d --build
```
