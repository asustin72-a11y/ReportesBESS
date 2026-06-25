# BESS — Reportes ION / BANCO

Aplicación Streamlit para monitoreo, análisis y reportes PDF de sistemas BESS (ION y BANCO).

**Versión actual:** 5.3 — recibo simulado CFE, descarga PDF (Playwright) y cargo FP con redondeo a 3 decimales.

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

### Datos

La app incluye CSV procesados en `data/` para arrancar con datos de ejemplo. El rol **admin** puede subir archivos fuente y regenerar reportes desde el sidebar.
