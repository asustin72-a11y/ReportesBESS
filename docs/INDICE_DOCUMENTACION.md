# Documentación — Sistema BESS

**Versión de la aplicación:** 5.12.0

## Manuales

| Documento | Formato | Audiencia | Descripción |
|-----------|---------|-----------|-------------|
| [Guía de usuario](GUIA_USUARIO.md) | Markdown · [PDF](GUIA_USUARIO.pdf) | Visualizador y operador | Reporteador: secciones, métricas, reportes PDF, recibo CFE |
| [Guía del administrador](GUIA_ADMINISTRADOR.md) | Markdown · [PDF](GUIA_ADMINISTRADOR.pdf) | Admin y superadmin | Pipeline de datos, sidebar, catálogo SQLite, mantenimiento BD |

## Generar los PDF

Con la app en ejecución (`streamlit run streamlit_app.py`):

```bash
python docs/generar_guia_pdf.py
python docs/generar_guia_admin_pdf.py
```

Sin capturas nuevas (reutiliza imágenes en `docs/capturas/`):

```bash
set BESS_SKIP_CAPTURE=1
python docs/generar_guia_pdf.py
python docs/generar_guia_admin_pdf.py
```

URL alternativa para capturas:

```bash
set BESS_APP_URL=https://tu-servidor:8501
python docs/generar_guia_pdf.py
```

## Operación e infraestructura

| Documento | Contenido |
|-----------|-----------|
| [README.md](../README.md) | Instalación, credenciales por defecto, despliegue |
| [DOCKER.md](DOCKER.md) | Despliegue con Docker Compose en servidor |
| [RESTAURACION_LOCAL.md](../RESTAURACION_LOCAL.md) | Restaurar datos y respaldos locales |
| [bess/ARCHITECTURE.md](../bess/ARCHITECTURE.md) | Arquitectura del código |
| [bess/PLAN_MIGRACION_SQLITE.md](../bess/PLAN_MIGRACION_SQLITE.md) | Plan de migración de CSV a SQLite en el pipeline |

## Herramientas ION

| Documento | Contenido |
|-----------|-----------|
| [GUIA_ION.md](GUIA_ION.md) | Uso del medidor ION y perfiles Modbus |
| [DESCARGAR_ION.md](DESCARGAR_ION.md) | Ejecutable `descargar_ion.exe` |
| [DESCARGAR_ION.pdf](DESCARGAR_ION.pdf) | Mismo contenido en PDF |

## Notas de versión

| Versión | Archivo |
|---------|---------|
| 5.12.0 | [RELEASE_NOTES_5.12.0.md](../RELEASE_NOTES_5.12.0.md) |
| 5.11.0 | [RELEASE_NOTES_5.11.0.md](../RELEASE_NOTES_5.11.0.md) |
| 5.10.0 | [RELEASE_NOTES_5.10.0.md](../RELEASE_NOTES_5.10.0.md) |
| 5.9.0 | [RELEASE_NOTES_5.9.0.md](../RELEASE_NOTES_5.9.0.md) |
| 5.8.0 | [RELEASE_NOTES_5.8.0.md](../RELEASE_NOTES_5.8.0.md) |
| 5.7.0 | [RELEASE_NOTES_5.7.0.md](../RELEASE_NOTES_5.7.0.md) |
| Anteriores | `RELEASE_NOTES_5.6.*.md` en la raíz del repositorio |

## Capturas de pantalla

Las imágenes del manual viven en `docs/capturas/`. El script `generar_guia_pdf.py` las actualiza automáticamente si la app está accesible en `http://localhost:8501` (o `BESS_APP_URL`).
