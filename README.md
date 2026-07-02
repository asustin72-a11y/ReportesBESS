# BESS — Reportes ION / BANCO

Aplicación Streamlit para monitoreo, análisis y reportes PDF de sistemas BESS (ION y BANCO).

**Versión actual:** 5.6.4 — Superadmin, Mantenimiento DB, preflight reloj en cron.

## Ejecución local

```bash
pip install -r requirements.txt
python -m playwright install chromium
streamlit run streamlit_app.py
```

## Despliegue en Streamlit Community Cloud

1. Sube este repositorio a GitHub: [ReportesBESS](https://github.com/asustin72-a11y/ReportesBESS)
2. Entra en [share.streamlit.io](https://share.streamlit.io) con tu cuenta de GitHub
3. **New app** → selecciona el repo `ReportesBESS`, rama `main`
4. **Main file path:** `streamlit_app.py`
5. Deploy

### Credenciales por defecto

| Usuario | Contraseña | Rol   |
|---------|------------|-------|
| admin   | admin123   | Admin |
| user    | user123    | User  |

Cambia estas contraseñas antes de compartir la app en producción.

### Despliegue en servidor Linux (Docker)

Ver [docs/DOCKER.md](docs/DOCKER.md) — `docker compose up -d` en el VPS con volúmenes `data/` y `deploy/secrets.toml`.

### Descarga de perfil ION (ejecutable)

Herramienta standalone para descargar el perfil de carga de un medidor ION por Modbus (sin Python en el equipo destino):

- **Ejecutable:** `dist/descargar_ion.exe` (generar con `scripts/build_descargar_ion.ps1`)
- **Documentación:** [docs/DESCARGAR_ION.md](docs/DESCARGAR_ION.md) · PDF: [docs/DESCARGAR_ION.pdf](docs/DESCARGAR_ION.pdf)

```powershell
cd C:\MisDescargas
C:\BESS\dist\descargar_ion.exe 172.16.111.209 2026-05-01
```

### Datos

La app incluye CSV procesados en `data/` para arrancar con datos de ejemplo. El rol **admin** puede subir archivos fuente y regenerar reportes desde el sidebar.
