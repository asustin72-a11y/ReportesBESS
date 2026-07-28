"""Constantes del reporteador Granja Solar IUSASOL."""

from __future__ import annotations

FECHA_INICIO_SYNC = "2026-01-01"
CAPACIDAD_MW = 22.0
ESQUEMA_TARIFA = "DIST"
GRUPO_GENERACION = "Generacion_IUSA_2"
INTERVALO_MIN = 5
# kW ≈ kWh × (60 / intervalo) para slots cincuminutales.
FACTOR_KW_DESDE_KWH = 60 / INTERVALO_MIN

NOMBRE_APP = "Reporteador Granja Solar IUSASOL"
TECHO_MW = CAPACIDAD_MW
