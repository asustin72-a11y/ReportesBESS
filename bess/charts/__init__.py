"""Figuras Plotly reutilizables (sin Streamlit)."""

from bess.charts.capacity import graficar_comparacion_capacidad, graficar_criterio_cfe
from bess.charts.energy import graficar_arbitraje, graficar_costo_energia_periodo
from bess.charts.layout import color_periodo, sanear_figura_plotly
from bess.charts.profile import graficar_demanda_dia, graficar_demanda_real_dia, graficar_perfil, muestra_grafica_demanda_real_dist
from bess.charts.trends import (
    graficar_energia_diaria_por_periodo,
    graficar_tendencia_arbitraje,
    graficar_tendencia_bess_operacion,
    graficar_tendencia_con_sin_bess,
    graficar_tendencia_consumo_periodo,
)

__all__ = [
    'color_periodo',
    'sanear_figura_plotly',
    'graficar_arbitraje',
    'graficar_comparacion_capacidad',
    'graficar_costo_energia_periodo',
    'graficar_criterio_cfe',
    'graficar_demanda_dia',
    'graficar_demanda_real_dia',
    'graficar_perfil',
    'muestra_grafica_demanda_real_dist',
    'graficar_energia_diaria_por_periodo',
    'graficar_tendencia_arbitraje',
    'graficar_tendencia_bess_operacion',
    'graficar_tendencia_con_sin_bess',
    'graficar_tendencia_consumo_periodo',
]
