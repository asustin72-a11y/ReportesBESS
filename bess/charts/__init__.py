"""Figuras Plotly reutilizables (sin Streamlit)."""

from bess.charts.capacity import graficar_comparacion_capacidad, graficar_criterio_cfe
from bess.charts.energy import graficar_arbitraje, graficar_costo_energia_periodo
from bess.charts.layout import color_periodo
from bess.charts.profile import graficar_demanda_dia, graficar_perfil
from bess.charts.trends import (
    graficar_tendencia_arbitraje,
    graficar_tendencia_bess_operacion,
    graficar_tendencia_con_sin_bess,
    graficar_tendencia_consumo_periodo,
)

__all__ = [
    'color_periodo',
    'graficar_arbitraje',
    'graficar_comparacion_capacidad',
    'graficar_costo_energia_periodo',
    'graficar_criterio_cfe',
    'graficar_demanda_dia',
    'graficar_perfil',
    'graficar_tendencia_arbitraje',
    'graficar_tendencia_bess_operacion',
    'graficar_tendencia_con_sin_bess',
    'graficar_tendencia_consumo_periodo',
]
