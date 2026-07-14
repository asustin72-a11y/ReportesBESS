"""Reglas CFE: temporada, periodos, costos y arbitraje."""

from bess.cfe.arbitrage import calcular_arbitraje_dia
from bess.cfe.capacity import calcular_criterio_cfe, construir_tabla_criterio_cfe
from bess.cfe.daily_data import energia_diaria_tiene_sin_bess, fila_por_fecha_csv, obtener_bess_energia_dia
from bess.cfe.energy import calcular_costo_energia_dia
from bess.cfe.energy_month import (
    calcular_arbitraje_desde_costos,
    calcular_costo_energia_mes,
    calcular_costo_energia_rango,
)
from bess.cfe.power_factor import calcular_cargo_fp, calcular_factor_potencia_pct
from bess.cfe.receipt import construir_datos_recibo_cfe, generar_recibo_pdf_bytes
from bess.cfe.periods import (
    agregar_periodo,
    es_festivo,
    obtener_periodo_por_fecha_hora,
    obtener_periodo_por_hora,
    obtener_temporada,
)

__all__ = [
    "agregar_periodo",
    "calcular_arbitraje_dia",
    "calcular_costo_energia_dia",
    "energia_diaria_tiene_sin_bess",
    "es_festivo",
    "fila_por_fecha_csv",
    "obtener_bess_energia_dia",
    "obtener_periodo_por_fecha_hora",
    "obtener_periodo_por_hora",
    "obtener_temporada",
]
