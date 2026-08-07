# Consultar Tarifa (IUSASOL)

App hermana de la suite de reporteadores (mismo patrón que Granja / Análisis de Perfil):
**Streamlit** independiente con **login BESS** compartido.

## Alcance

- Consulta de cuotas vigentes en `app.cfe.mx` (Hogar, Negocio, Industria, Agrícola)
- Descarga de reportes CSV ya generados en `data/ReportesTarifasCFE`
- **Solo lectura**: no escribe SQLite ni actualiza el catálogo BESS
- La actualización automática DIST/GDMTH de BESS sigue por cron (`scripts/cron_actualizar_tarifas_bess.sh`)

## Ejecución (desarrollo local)

Desde la raíz de `ReporteadorIUSASOL`:

```bash
pip install -r requirements.txt
python -m playwright install chromium
streamlit run streamlit_tarifas_cfe.py
```

Puerto opcional: `--server.port 8503`.

Credenciales: las mismas que BESS / Granja (`catalog_usuarios` / secrets).

## Estructura

```
tarifas_cfe/
  __init__.py       # NOMBRE_APP, VERSION
  ui/               # Streamlit (app, pages)
streamlit_tarifas_cfe.py
```

Reutiliza el cliente CFE de `bess.data.ingest.cfe`.

## Relación con la suite

- App hermana (no se embebe vía `modo_vista`).
- Si la sesión trae `suite_modulo`, muestra **Volver a la Suite**.
