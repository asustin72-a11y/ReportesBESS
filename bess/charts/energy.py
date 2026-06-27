"""Costos de energía y arbitraje por periodo."""

from __future__ import annotations

import plotly.graph_objects as go

from bess.cfe.energy_month import PERIODOS_ENERGIA
from bess.charts.layout import _titulo_y_leyenda_externos
from bess.charts.styles import _aplicar_estilo_grafica_comparativa
from bess.config.theme import COLORES


def graficar_costo_energia_periodo(res_con, res_sin):
    periodos = [lbl for _, lbl in PERIODOS_ENERGIA]
    costo_sin = [res_sin['por_periodo'][k]['costo_mxn'] for k, _ in PERIODOS_ENERGIA]
    costo_con = [res_con['por_periodo'][k]['costo_mxn'] for k, _ in PERIODOS_ENERGIA]
    fig = go.Figure()
    fig.add_trace(go.Bar(
        name='Con BESS',
        x=periodos,
        y=costo_con,
        marker_color=COLORES['success'],
        text=[f'${v:,.2f}' for v in costo_con],
        textposition='outside',
        cliponaxis=False,
    ))
    fig.add_trace(go.Bar(
        name='Sin BESS',
        x=periodos,
        y=costo_sin,
        marker_color=COLORES['danger'],
        text=[f'${v:,.2f}' for v in costo_sin],
        textposition='outside',
        cliponaxis=False,
    ))
    _aplicar_estilo_grafica_comparativa(
        fig,
        'Costo de energía acumulado por periodo',
        'MXN',
        y_tickprefix='$',
    )
    return fig


def graficar_arbitraje(arbitraje_data, titulo):
    periodos = ['Base', 'Intermedio', 'Punta']
    valores = [arbitraje_data['arbitraje'].get(p, 0) for p in periodos]
    colores = ['#3498db', '#f1c40f', '#e74c3c']

    fig = go.Figure()
    fig.add_trace(go.Bar(
        x=periodos,
        y=valores,
        text=[f'${v:,.2f}' for v in valores],
        textposition='outside',
        marker=dict(color=colores, line=dict(color='white', width=1))
    ))
    fig.add_hline(y=0, line=dict(color='#4a5568', width=1, dash='dash'))

    title_cfg, _, margin_t = _titulo_y_leyenda_externos(titulo, show_legend=False)
    fig.update_layout(
        title=title_cfg,
        xaxis_title='Periodo',
        yaxis_title='Arbitraje ($)',
        height=350,
        showlegend=False,
        margin=dict(l=50, r=20, t=margin_t, b=40),
    )

    return fig
