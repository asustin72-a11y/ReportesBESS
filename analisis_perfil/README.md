# Análisis de Perfil (IUSASOL)

App hermana de la suite de reporteadores (mismo patrón que Granja): procesoStreamlit** independiente con **login BESS** compartido.

## Alcance

- Análisis de perfiles cincominutales (CSV/ZIP o descarga API)
- Tarifas **T01**, **GDMTH** y **DIST**
- Servicios: Consumo, Generación, Bidireccional, Neteo
- Resumen energético, costos/ahorro, calidad de datos, demanda pico, PDF y CSV recibo-ready
- Controles en el **área principal** (no depende de la sidebar de la suite)

## Ejecución (desarrollo local)

Desde la raíz de `ReporteadorIUSASOL`:

```bash
pip install -r requirements.txt
streamlit run streamlit_analisis_perfil.py
```

Credenciales: las mismas que BESS / Granja (`catalog_usuarios` / secrets).

Secretos API (descargas embebidas): `.streamlit/secrets.toml` o `deploy/secrets.toml` → `[iusasol]`.

## Estructura

```
analisis_perfil/
  paths.py          # rutas in-repo (trabajo, ReportesTarifasCFE)
  theme.py          # tarifas / servicios / colores
  ui/               # Streamlit (app, pages, bridge API)
  *.py              # pipeline (diario, tipicos, tarifas, PDF…)
  tarifas_*.csv     # catálogo histórico T01/DIST/GDMTH
streamlit_analisis_perfil.py
```

Jobs temporales: `data/analisis_perfil_trabajo/`.

## Relación con la suite

- **No** se embebe vía `modo_vista` (eso es Descargas).
- Si la sesión trae `suite_modulo`, muestra **Volver a la Suite**.
- Reutiliza `descargas` y `data/ReportesTarifasCFE` del mismo repo.
