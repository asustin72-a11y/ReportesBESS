# IUSASOL — Reportes y consultas

Repositorio de sistemas IUSASOL:

| Módulo | Entrada | Estado |
|--------|---------|--------|
| **BESS** | `streamlit run streamlit_app.py` | Producción — reportes BESS (ION / BANCO) |
| **Consultas Usuarios** | `streamlit run streamlit_consultas_usuarios.py` | En diseño — contratos / medidores / perfiles API ISOL |

Ver [docs/CONSULTAS_USUARIOS.md](docs/CONSULTAS_USUARIOS.md).

**Ruta local Windows:** `C:\Proyectos_IUSASOL\ReporteadorIUSASOL`

---

# BESS — Reportes ION / BANCO

Aplicación Streamlit para monitoreo, análisis y reportes PDF de sistemas BESS (ION y BANCO).

**Versión actual:** 5.14.0 — Mantenimiento DB: pcarga Ethernet, Rebuild CSV, reconciliar e import protegido.

## Documentación

| Documento | Descripción |
|-----------|-------------|
| [docs/INDICE_DOCUMENTACION.md](docs/INDICE_DOCUMENTACION.md) | Índice de manuales y notas de versión |
| [docs/GUIA_USUARIO.md](docs/GUIA_USUARIO.md) · [PDF](docs/GUIA_USUARIO.pdf) | Manual del reporteador |
| [docs/GUIA_ADMINISTRADOR.md](docs/GUIA_ADMINISTRADOR.md) · [PDF](docs/GUIA_ADMINISTRADOR.pdf) | Pipeline, superadmin, catálogo, cursores, reconciliación y Rebuild CSV |
| [docs/DOCKER.md](docs/DOCKER.md) | Despliegue Docker |

Regenerar PDFs: `python docs/generar_guia_pdf.py` y `python docs/generar_guia_admin_pdf.py` (app en `localhost:8501` para capturas nuevas).

## Ejecución local

```bash
pip install -r requirements.txt
python -m playwright install chromium
streamlit run streamlit_app.py
```

## Pruebas

Suite unitaria sobre `bess/core`, `bess/cfe` y `bess/tariffs` (sin levantar la app ni tocar datos reales):

```bash
pip install -r requirements-dev.txt
pytest
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

El rol `superadmin` se configura en `deploy/secrets.toml` o desde el catálogo
de usuarios. No se publica una contraseña predeterminada en este documento.
Cambia todas las credenciales iniciales antes de compartir la app.

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

La app incluye CSV procesados en `data/` para arrancar con datos de ejemplo.
El rol **admin** puede sincronizar, subir fuentes y regenerar reportes. El rol
**superadmin** agrega catálogo, usuarios y Mantenimiento DB: importar/exportar
SQLite, revisar cursores y `sync_log`, reconciliar BD↔Fuente, ejecutar Rebuild
CSV y purgar perfiles.
