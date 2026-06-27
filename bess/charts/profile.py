"""Perfil de carga y demanda rodante."""

from __future__ import annotations

import pandas as pd
import plotly.graph_objects as go

from bess.charts.layout import _titulo_y_leyenda_externos
from bess.config.theme import COLORES


def graficar_perfil(df, prefijo, titulo):
    """Grafica el perfil de carga. Un día: eje X por hora. Varios días: eje X por día (máx. diario)."""
    df = df.copy()
    if 'DATETIME' not in df.columns:
        df['DATETIME'] = pd.to_datetime(df['FECHA_HORA'], format='%d/%m/%Y %H:%M')

    col_con = f'IUSA_CON_BESS_{prefijo}_kW'
    if col_con not in df.columns:
        for col in df.columns:
            if 'IUSA_CON_BESS' in col and prefijo in col:
                col_con = col
                break

    multidia = df['DATETIME'].dt.date.nunique() > 1

    if multidia:
        agg_cols = [c for c in [col_con, 'BESS_REC_kW', 'BESS_ENT_kW'] if c in df.columns]
        df['FECHA_DIA'] = df['DATETIME'].dt.date
        df_plot = df.groupby('FECHA_DIA', as_index=False)[agg_cols].max()
        df_plot['FECHA_DIA'] = pd.to_datetime(df_plot['FECHA_DIA'])
        x_vals = df_plot['FECHA_DIA']
        x_title = 'Día'
        x_tickformat = '%d/%m/%Y'
        x_dtick = 86400000
        marker_size = 7
        titulo_suffix = ' (máx. diario)' if titulo else ''
    else:
        df_plot = df
        x_vals = df['DATETIME']
        x_title = 'Hora'
        x_tickformat = '%H:%M'
        x_dtick = 7200000
        marker_size = 0
        titulo_suffix = ''

    fig = go.Figure()
    trace_mode = 'lines+markers' if multidia else 'lines'

    if col_con in df_plot.columns:
        fig.add_trace(go.Scatter(
            x=x_vals,
            y=df_plot[col_con],
            name=f'IUSA Con BESS ({prefijo})',
            mode=trace_mode,
            line=dict(color=COLORES['primary'], width=2.5),
            marker=dict(size=marker_size, color=COLORES['primary']),
            fill='tozeroy',
            fillcolor='rgba(26,82,118,0.12)'
        ))

    if 'BESS_REC_kW' in df_plot.columns:
        fig.add_trace(go.Scatter(
            x=x_vals,
            y=df_plot['BESS_REC_kW'],
            name='Carga BESS',
            mode=trace_mode,
            line=dict(color=COLORES['carga'], width=2),
            marker=dict(size=marker_size, color=COLORES['carga']),
            fill='tozeroy',
            fillcolor='rgba(46,204,113,0.12)'
        ))

    if 'BESS_ENT_kW' in df_plot.columns:
        fig.add_trace(go.Scatter(
            x=x_vals,
            y=-df_plot['BESS_ENT_kW'],
            name='Descarga BESS',
            mode=trace_mode,
            line=dict(color=COLORES['danger'], width=2),
            marker=dict(size=marker_size, color=COLORES['danger']),
            fill='tozeroy',
            fillcolor='rgba(231,76,60,0.12)'
        ))

    titulo_grafica = f"{titulo}{titulo_suffix}".strip()
    title_cfg, legend_cfg, margin_t = _titulo_y_leyenda_externos(titulo_grafica)
    fig.update_layout(
        title=title_cfg,
        xaxis_title=x_title,
        yaxis_title='Potencia (kW)',
        height=420,
        hovermode='x unified',
        legend=legend_cfg,
        margin=dict(l=52, r=52, t=margin_t, b=40),
    )
    fig.update_xaxes(tickformat=x_tickformat, dtick=x_dtick)
    fig.update_yaxes(zeroline=True, zerolinecolor='#95a5a6', zerolinewidth=1)

    return fig


def graficar_demanda_dia(df, prefijo, titulo=''):
    """Compara demanda IUSA con y sin BESS (ventana rolling 15 min)."""
    df = df.copy()
    if 'DATETIME' not in df.columns:
        df['DATETIME'] = pd.to_datetime(df['FECHA_HORA'], format='%d/%m/%Y %H:%M')

    col_con = f'IUSA_CON_BESS_{prefijo}_kW_DEM_15min'
    col_sin = f'IUSA_SIN_BESS_{prefijo}_kW_DEM_15min'

    if col_con not in df.columns or col_sin not in df.columns:
        fig = go.Figure()
        fig.add_annotation(
            text="Columnas de demanda no disponibles",
            x=0.5, y=0.5, xref='paper', yref='paper', showarrow=False,
            font=dict(size=14, color='#718096')
        )
        fig.update_layout(height=420, margin=dict(l=50, r=20, t=50, b=40))
        return fig

    df[col_con] = pd.to_numeric(df[col_con], errors='coerce')
    df[col_sin] = pd.to_numeric(df[col_sin], errors='coerce')
    df_plot = df.dropna(subset=[col_con, col_sin]).sort_values('DATETIME')

    if df_plot.empty:
        fig = go.Figure()
        fig.add_annotation(
            text="Sin datos de demanda (15 min) para este día",
            x=0.5, y=0.5, xref='paper', yref='paper', showarrow=False,
            font=dict(size=14, color='#718096')
        )
        fig.update_layout(height=420, margin=dict(l=50, r=20, t=50, b=40))
        return fig

    fig = go.Figure()
    fig.add_trace(go.Scatter(
        x=df_plot['DATETIME'],
        y=df_plot[col_sin],
        name='Demanda sin BESS',
        mode='lines+markers',
        line=dict(color=COLORES['danger'], width=2, dash='dash'),
        marker=dict(size=5, color=COLORES['danger']),
    ))
    fig.add_trace(go.Scatter(
        x=df_plot['DATETIME'],
        y=df_plot[col_con],
        name='Demanda con BESS',
        mode='lines+markers',
        line=dict(color=COLORES['primary'], width=2.5),
        marker=dict(size=5, color=COLORES['primary']),
        fill='tonexty',
        fillcolor='rgba(39, 174, 96, 0.18)',
    ))

    titulo_grafica = titulo or f'Análisis de Demanda · {prefijo}'
    title_cfg, legend_cfg, margin_t = _titulo_y_leyenda_externos(titulo_grafica)
    fig.update_layout(
        title=title_cfg,
        xaxis_title='Hora',
        yaxis_title='Demanda (kW) · ventana 15 min',
        height=460,
        hovermode='x unified',
        legend=legend_cfg,
        margin=dict(l=55, r=25, t=margin_t, b=50),
    )
    fig.update_xaxes(tickformat='%H:%M', dtick=7200000)
    fig.update_yaxes(zeroline=True, zerolinecolor='#95a5a6', zerolinewidth=1)

    return fig
