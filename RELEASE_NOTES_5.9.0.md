# BESS 5.9.0

## Resumen

Rediseño de navegación por secciones, medidor de facturación por catálogo, rutas y columnas CSV con nombres canónicos, gráficas de Generación alineadas al resto de la app, y manuales de usuario/administrador actualizados.

## Cambios principales

### Navegación y UX
- Barra principal por **secciones** (Operación, Análisis, Participación, Tendencia, Generación, Reportes, Recibo) con sub-navegación interna.
- Ayuda contextual bajo la barra de navegación.
- Barra de contexto con chips de estado (subestación, medidor, periodo).
- Vista simplificada para rol **visualizador** (`user`).
- Breadcrumbs en modos admin (catálogo, mantenimiento BD).

### Medidor de facturación y catálogo
- Medidor **tipo 1** (facturación) como predeterminado al cambiar subestación.
- `MedidorConsumo.prefijo` = nombre catálogo (sin alias legacy `ION` / `BANCO` / `IUSA2`).
- Columnas de reportes y combinados usan nombre completo del medidor (ej. `KWH_REC_ION_Testigo_IUSA1`).
- kVArh según reglas de tipo en catálogo; recibo CFE indexado por nombre catálogo.

### Rutas y pipeline
- Rutas canónicas por subestación: `ArchivosFuente/{Sub}/`, `ArchivosProcesados/{Sub}/`, `ArchivosReporte/{Sub}/`.
- Eliminados fallbacks a CSV planos en raíz del proyecto.
- Estado del pipeline en sidebar (sync → verificar → filtrar → reportes).

### Generación
- Gráfica de barras reutiliza estilo de Tendencia (`graficar_energia_diaria_por_periodo`).
- Perfil intradiario con colores y layout unificados (`render_grafica_plotly`).
- Resumen del día (día único) con fila acumulada al mes.
- Unidades kWh visibles en vista de rango.

### Documentación
- [Guía del administrador](docs/GUIA_ADMINISTRADOR.md) y PDF.
- Índice de documentación (`docs/INDICE_DOCUMENTACION.md`).
- Capturas y manual de usuario regenerados.

## Migración desde 5.8.0

```bash
cd ~/ReportesBESS
git fetch --tags
git checkout -f v5.9.0
docker compose up -d --build
```

Tras actualizar, **regenerar reportes** si los CSV aún tienen columnas con prefijos legacy (`ION`, `BANCO`, `IUSA2`):

```bash
python scripts/sincronizar_perfiles.py --quiet --procesar
```

## Archivos nuevos

- `bess/ui/pipeline_status.py`
- `docs/GUIA_ADMINISTRADOR.md`, `docs/generar_guia_admin_pdf.py`, `docs/pdf_shared.py`
- `docs/INDICE_DOCUMENTACION.md`

## Versión anterior

- **5.8.0** — IUSA_ARAGON, catálogo SQLite, generación en perfil/PDF, sidebar oculta user.
