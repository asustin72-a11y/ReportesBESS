"""Visualización de gráficas Plotly con exportación PNG vía modebar."""

from __future__ import annotations

import re

import streamlit as st

from bess.charts.export import DEFAULT_PNG_SCALE

_MODEBAR_OCULTAR = (
    'zoom2d', 'pan2d', 'select2d', 'lasso2d', 'zoomIn2d', 'zoomOut2d',
    'autoScale2d', 'resetScale2d', 'hoverClosestCartesian', 'hoverCompareCartesian',
    'toggleSpikelines', 'resetViewMapbox', 'zoomInGeo', 'zoomOutGeo', 'resetGeo',
    'hoverClosestGeo', 'hoverClosestGl2d', 'hoverClosestPie', 'toggleHover',
    'sendDataToCloud', 'editInChartStudio',
)


def _nombre_png_seguro(nombre: str) -> str:
    base = re.sub(r'[^\w.\-]+', '_', nombre.strip())
    return base if base.lower().endswith('.png') else f'{base}.png'


def _plotly_config(nombre_png: str) -> dict:
    return {
        'displayModeBar': True,
        'displaylogo': False,
        'modeBarButtonsToRemove': list(_MODEBAR_OCULTAR),
        'toImageButtonOptions': {
            'format': 'png',
            'filename': _nombre_png_seguro(nombre_png).removesuffix('.png'),
            'scale': DEFAULT_PNG_SCALE,
        },
    }


def render_grafica_plotly(
    fig,
    nombre_png: str,
    download_key: str | None = None,
):
    """Muestra la gráfica; la descarga PNG usa el botón de la barra superior derecha."""
    kwargs = {
        'use_container_width': True,
        'config': _plotly_config(nombre_png),
    }
    if download_key:
        kwargs['key'] = f'plotly_{download_key}'
    st.plotly_chart(fig, **kwargs)
