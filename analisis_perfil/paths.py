"""Rutas del módulo Análisis de Perfil dentro de ReporteadorIUSASOL."""

from __future__ import annotations

from pathlib import Path

from bess.config.paths import PROJECT_ROOT

# Paquete (scripts del pipeline y CSV de tarifas locales).
DIR_PAQUETE = Path(__file__).resolve().parent

# Trabajo de jobs Streamlit (CSV generados por sesión).
DIR_TRABAJO = PROJECT_ROOT / "data" / "analisis_perfil_trabajo"

# Reportes CFE DIST/GDMTH de la suite.
DIR_REPORTES_TARIFAS_CFE = PROJECT_ROOT / "data" / "ReportesTarifasCFE"

# Caché local opcional de CSVs sincronizados.
DIR_TARIFAS_CFE_LOCAL = DIR_PAQUETE / "tarifas_cfe"
