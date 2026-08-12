# Documentación — Sistema BESS

**Versión de la aplicación:** 5.18.12

## Manuales

| Documento | Formato | Audiencia | Descripción |
|-----------|---------|-----------|-------------|
| [Manual de la Suite](MANUAL_SUITE.md) · [PDF](MANUAL_SUITE.pdf) | Markdown · PDF | Todos los roles | **Todas las opciones** del portal: BESS, Granja, Descargas, Análisis de Perfil y Consultar Tarifa |
| [Manual de catálogo](MANUAL_CATALOGO.md) · [PDF](MANUAL_CATALOGO.pdf) | Markdown · PDF | Superadmin | **Alta de medidores y subestaciones**: reglas, campos, ejemplos y pipeline post-alta |
| [Guía de usuario](GUIA_USUARIO.md) | Markdown · [PDF](GUIA_USUARIO.pdf) | Visualizador y operador | Detalle del reporteador BESS (métricas, PDF, recibo CFE y emisiones) |
| [Guía del administrador](GUIA_ADMINISTRADOR.md) | Markdown · [PDF](GUIA_ADMINISTRADOR.pdf) | Admin y superadmin | Pipeline, catálogo, importación, cursores, reconciliación, Rebuild CSV, purga y recuperación |

## Generar los PDF

Con la app en ejecución (`streamlit run streamlit_app.py`):

```bash
python docs/generar_guia_pdf.py
python docs/generar_guia_admin_pdf.py
python docs/generar_manual_suite_pdf.py
python docs/generar_manual_catalogo_pdf.py
```

Sin capturas nuevas (reutiliza imágenes en `docs/capturas/`):

```bash
set BESS_SKIP_CAPTURE=1
python docs/generar_guia_pdf.py
python docs/generar_guia_admin_pdf.py
```

Solo Suite o catálogo (desde Markdown, sin capturas):

```bash
python docs/generar_manual_suite_pdf.py
python docs/generar_manual_catalogo_pdf.py
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
| 5.18.12 | [RELEASE_NOTES_5.18.12.md](../RELEASE_NOTES_5.18.12.md) |
| 5.18.11 | [RELEASE_NOTES_5.18.11.md](../RELEASE_NOTES_5.18.11.md) |
| 5.18.10 | [RELEASE_NOTES_5.18.10.md](../RELEASE_NOTES_5.18.10.md) |
| 5.18.9 | [RELEASE_NOTES_5.18.9.md](../RELEASE_NOTES_5.18.9.md) |
| 5.18.8 | [RELEASE_NOTES_5.18.8.md](../RELEASE_NOTES_5.18.8.md) |
| 5.18.7 | [RELEASE_NOTES_5.18.7.md](../RELEASE_NOTES_5.18.7.md) |
| 5.18.6 | [RELEASE_NOTES_5.18.6.md](../RELEASE_NOTES_5.18.6.md) |
| 5.18.5 | [RELEASE_NOTES_5.18.5.md](../RELEASE_NOTES_5.18.5.md) |
| 5.18.4 | [RELEASE_NOTES_5.18.4.md](../RELEASE_NOTES_5.18.4.md) |
| 5.18.3 | [RELEASE_NOTES_5.18.3.md](../RELEASE_NOTES_5.18.3.md) |
| 5.18.2 | [RELEASE_NOTES_5.18.2.md](../RELEASE_NOTES_5.18.2.md) |
| 5.18.1 | [RELEASE_NOTES_5.18.1.md](../RELEASE_NOTES_5.18.1.md) |
| 5.18.0 | [RELEASE_NOTES_5.18.0.md](../RELEASE_NOTES_5.18.0.md) |
| 5.17.0 | [RELEASE_NOTES_5.17.0.md](../RELEASE_NOTES_5.17.0.md) |
| 5.16.1 | [RELEASE_NOTES_5.16.1.md](../RELEASE_NOTES_5.16.1.md) |
| 5.16.0 | [RELEASE_NOTES_5.16.0.md](../RELEASE_NOTES_5.16.0.md) |
| 5.15.0 | [RELEASE_NOTES_5.15.0.md](../RELEASE_NOTES_5.15.0.md) |
| 5.14.0 | [RELEASE_NOTES_5.14.0.md](../RELEASE_NOTES_5.14.0.md) |
| 5.13.0 | [RELEASE_NOTES_5.13.0.md](../RELEASE_NOTES_5.13.0.md) |
| 5.12.0 | [RELEASE_NOTES_5.12.0.md](../RELEASE_NOTES_5.12.0.md) |
| 5.11.0 | [RELEASE_NOTES_5.11.0.md](../RELEASE_NOTES_5.11.0.md) |
| 5.10.0 | [RELEASE_NOTES_5.10.0.md](../RELEASE_NOTES_5.10.0.md) |
| 5.9.0 | [RELEASE_NOTES_5.9.0.md](../RELEASE_NOTES_5.9.0.md) |
| 5.8.0 | [RELEASE_NOTES_5.8.0.md](../RELEASE_NOTES_5.8.0.md) |
| 5.7.0 | [RELEASE_NOTES_5.7.0.md](../RELEASE_NOTES_5.7.0.md) |
| Anteriores | `RELEASE_NOTES_5.6.*.md` en la raíz del repositorio |

## Capturas de pantalla

Las imágenes del manual viven en `docs/capturas/`. El script `generar_guia_pdf.py` las actualiza automáticamente si la app está accesible en `http://localhost:8501` (o `BESS_APP_URL`).
