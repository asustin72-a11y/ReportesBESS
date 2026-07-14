"""Gráficas de capacidad CFE."""

from __future__ import annotations

import plotly.graph_objects as go

from bess.charts.layout import _titulo_y_leyenda_externos
from bess.charts.styles import _aplicar_estilo_grafica_comparativa
from bess.config.theme import COLORES


def graficar_comparacion_capacidad(capacidad_sin, capacidad_con, ahorro):
    fig = go.Figure()
    fig.add_trace(go.Bar(
        x=[capacidad_sin, capacidad_con],
        y=['Sin BESS', 'Con BESS'],
        orientation='h',
        marker_color=['#e74c3c', '#27ae60'],
        text=[f'${capacidad_sin:,.2f}', f'${capacidad_con:,.2f}'],
        textposition='outside',
        cliponaxis=False,
    ))
    title_cfg, _, margin_t = _titulo_y_leyenda_externos(
        'Comparación de costo por capacidad (criterio CFE)', font_size=14, show_legend=False,
    )
    fig.update_layout(
        title=title_cfg,
        xaxis_title='MXN',
        height=220,
        margin=dict(l=10, r=80, t=margin_t, b=20),
        showlegend=False,
        plot_bgcolor='rgba(0,0,0,0)',
        paper_bgcolor='rgba(0,0,0,0)',
    )
    fig.update_xaxes(tickformat=',.0f', gridcolor='#eef2f6')
    fig.update_yaxes(tickfont=dict(size=12))
    if ahorro > 0:
        fig.add_annotation(
            x=max(capacidad_sin, capacidad_con) * 0.55,
            y=0.5,
            text=f'▼ Ahorro ${ahorro:,.2f}',
            showarrow=False,
            font=dict(size=13, color='#1e8449', weight='bold'),
            bgcolor='rgba(232, 248, 239, 0.95)',
            bordercolor='#27ae60',
            borderwidth=1,
            borderpad=6,
        )
    return fig


def graficar_criterio_cfe(resultado_con, resultado_sin=None):
    """Barras agrupadas: verde = Con BESS, rojo = Sin BESS."""
    categorias = ['Demanda punta', 'DemandaCalculadaCFE', 'Capacidad CFE']
    fig = go.Figure()

    if resultado_con is not None:
        valores = [
            resultado_con['criterio1_punta_kw'],
            resultado_con['criterio2_factor_kw'],
            resultado_con['capacidad_kw'],
        ]
        fig.add_trace(go.Bar(
            name='Con BESS',
            x=categorias,
            y=valores,
            marker_color=COLORES['success'],
            text=[f"{v:,.0f}" for v in valores],
            textposition='outside',
            cliponaxis=False,
        ))
    if resultado_sin is not None:
        valores = [
            resultado_sin['criterio1_punta_kw'],
            resultado_sin['criterio2_factor_kw'],
            resultado_sin['capacidad_kw'],
        ]
        fig.add_trace(go.Bar(
            name='Sin BESS',
            x=categorias,
            y=valores,
            marker_color=COLORES['danger'],
            text=[f"{v:,.0f}" for v in valores],
            textposition='outside',
            cliponaxis=False,
        ))

    _aplicar_estilo_grafica_comparativa(
        fig,
        'Criterio CFE · comparación de criterios (kW)',
        'kW',
    )
    return fig
