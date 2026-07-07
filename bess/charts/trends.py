"""Gráficas de tendencia diaria."""

from __future__ import annotations

import pandas as pd
import plotly.graph_objects as go

from bess.cfe.periods import es_festivo
from bess.charts.styles import _aplicar_estilo_grafica_tendencia, _hex_a_rgba
from bess.config.theme import COLORES

LEYENDA_DIA_ARBITRAJE = (
    ('día laboral', 'Lun–vie', COLORES['success']),
    ('sábado', 'Sábado', COLORES['secondary']),
    ('domingo_festivo', 'Domingo / Festivo', COLORES['danger']),
)


def _tipo_dia_arbitraje(fecha_dt):
    """Clasifica el día para colorear barras de arbitraje."""
    fecha = fecha_dt.date() if hasattr(fecha_dt, 'date') else fecha_dt
    if es_festivo(fecha) or fecha.weekday() == 6:
        return 'domingo_festivo'
    if fecha.weekday() == 5:
        return 'sábado'
    return 'día laboral'


def _ancho_barras_arbitraje(df):
    """Ancho de barra (ms) y bargap según cantidad de días; evita solapamiento entre días adyacentes."""
    n = max(len(df), 1)
    ms_dia = 86_400_000
    fechas = df['FECHA_DT'].sort_values().reset_index(drop=True)
    if n == 1:
        return ms_dia * 0.55, 0.82

    diffs_ms = fechas.diff().dropna().dt.total_seconds() * 1000
    min_paso_ms = float(diffs_ms.min()) if not diffs_ms.empty else ms_dia
    if min_paso_ms <= 0:
        min_paso_ms = ms_dia

    ocupacion = min(0.72, 0.38 + 6.0 / n)
    ancho_ms = min(ms_dia * 0.72, min_paso_ms * ocupacion)
    bargap = max(0.04, min(0.45, 0.50 - n * 0.01))
    return ancho_ms, bargap


def _rango_eje_y_arbitraje(serie, margen=0.15):
    """Eje Y con ±margen respecto al valor extremo del rango."""
    vals = pd.to_numeric(serie, errors='coerce').dropna()
    if vals.empty:
        return None
    y_min, y_max = float(vals.min()), float(vals.max())
    pico = max(abs(y_min), abs(y_max))
    if pico == 0:
        return [-1, 1]
    pad = pico * margen
    return [y_min - pad, y_max + pad]


def _mapas_leyenda_arbitraje():
    color_map = {k: c for k, _, c in LEYENDA_DIA_ARBITRAJE}
    label_map = {k: lbl for k, lbl, _ in LEYENDA_DIA_ARBITRAJE}
    return color_map, label_map


_COLS_ENERGIA_PERIODO = [
    ('BASE_REC', 'Base', COLORES['base']),
    ('INTERMEDIO_REC', 'Intermedio', COLORES['intermedio']),
    ('PUNTA_REC', 'Punta', COLORES['punta']),
]


def graficar_energia_diaria_por_periodo(df, titulo):
    """Barras apiladas Base / Intermedio / Punta por día (estilo unificado)."""
    fig = go.Figure()
    for col, lbl, color in _COLS_ENERGIA_PERIODO:
        y = pd.to_numeric(df[col], errors='coerce').fillna(0)
        fig.add_trace(go.Bar(
            x=df['FECHA_DT'],
            y=y,
            name=lbl,
            marker=dict(
                color=color,
                line=dict(width=0.5, color='white'),
            ),
            hovertemplate=f'<b>{lbl}</b><br>%{{x|%d/%m/%Y}}<br>%{{y:,.0f}} kWh<extra></extra>',
        ))
    fig.update_layout(barmode='stack', bargap=0.15)
    total_diario = sum(
        pd.to_numeric(df[c[0]], errors='coerce').fillna(0) for c in _COLS_ENERGIA_PERIODO
    )
    y_max = float(total_diario.max()) if len(total_diario) else 0
    yaxis_range = [0, y_max * 1.08] if y_max > 0 else None
    return _aplicar_estilo_grafica_tendencia(fig, titulo, 'kWh', yaxis_range=yaxis_range)


def graficar_tendencia_consumo_periodo(df, rango_label):
    return graficar_energia_diaria_por_periodo(
        df, f'Consumo diario por periodo · {rango_label}',
    )


def graficar_tendencia_con_sin_bess(df, rango_label):
    fig = go.Figure()
    fig.add_trace(go.Scatter(
        x=df['FECHA_DT'], y=df['TOTAL_CON'], name='Con BESS',
        mode='lines+markers',
        line=dict(color=COLORES['success'], width=2.5),
        marker=dict(size=6, color=COLORES['success'], line=dict(width=1, color='white')),
        hovertemplate='<b>Con BESS</b><br>%{x|%d/%m/%Y}<br>%{y:,.0f} kWh<extra></extra>',
    ))
    fig.add_trace(go.Scatter(
        x=df['FECHA_DT'], y=df['TOTAL_SIN'], name='Sin BESS',
        mode='lines+markers',
        line=dict(color=COLORES['danger'], width=2, dash='dot'),
        marker=dict(size=6, color=COLORES['danger'], line=dict(width=1, color='white')),
        hovertemplate='<b>Sin BESS</b><br>%{x|%d/%m/%Y}<br>%{y:,.0f} kWh<extra></extra>',
    ))
    ahorro = df['TOTAL_SIN'] - df['TOTAL_CON']
    fig.add_trace(go.Bar(
        x=df['FECHA_DT'], y=ahorro, name='Ahorro diario',
        marker=dict(
            color=_hex_a_rgba(COLORES['success'], 0.45),
            line=dict(color=_hex_a_rgba(COLORES['success'], 0.85), width=0.5),
            cornerradius=3,
        ),
        yaxis='y2',
        hovertemplate='<b>Ahorro</b><br>%{x|%d/%m/%Y}<br>%{y:,.0f} kWh<extra></extra>',
    ))
    fig.update_layout(
        yaxis2=dict(
            title='Δ kWh',
            title_font=dict(size=12, color='#718096'),
            tickfont=dict(size=10, color='#718096'),
            overlaying='y',
            side='right',
            showgrid=False,
            zeroline=False,
        ),
        bargap=0.35,
    )
    return _aplicar_estilo_grafica_tendencia(
        fig, f'Consumo con vs sin BESS · {rango_label}', 'kWh', yaxis_range=[0, 300_000],
    )


def graficar_tendencia_bess_operacion(df_bess, rango_label):
    carga = (
        pd.to_numeric(df_bess['BASE_REC'], errors='coerce').fillna(0)
        + pd.to_numeric(df_bess['INTERMEDIO_REC'], errors='coerce').fillna(0)
        + pd.to_numeric(df_bess['PUNTA_REC'], errors='coerce').fillna(0)
    )
    descarga = (
        pd.to_numeric(df_bess['BASE_ENT'], errors='coerce').fillna(0)
        + pd.to_numeric(df_bess['INTERMEDIO_ENT'], errors='coerce').fillna(0)
        + pd.to_numeric(df_bess['PUNTA_ENT'], errors='coerce').fillna(0)
    )
    fig = go.Figure()
    fig.add_trace(go.Bar(
        x=df_bess['FECHA_DT'], y=carga, name='Carga BESS',
        marker=dict(
            color=COLORES['carga'],
            line=dict(color='rgba(255,255,255,0.7)', width=0.5),
            cornerradius=4,
        ),
        hovertemplate='<b>Carga BESS</b><br>%{x|%d/%m/%Y}<br>%{y:,.0f} kWh<extra></extra>',
    ))
    fig.add_trace(go.Bar(
        x=df_bess['FECHA_DT'], y=descarga, name='Descarga BESS',
        marker=dict(
            color=COLORES['descarga'],
            line=dict(color='rgba(255,255,255,0.7)', width=0.5),
            cornerradius=4,
        ),
        hovertemplate='<b>Descarga BESS</b><br>%{x|%d/%m/%Y}<br>%{y:,.0f} kWh<extra></extra>',
    ))
    fig.update_layout(barmode='group', bargap=0.15, bargroupgap=0.08)
    return _aplicar_estilo_grafica_tendencia(
        fig, f'Carga y descarga BESS · {rango_label}', 'kWh', yaxis_range=[0, 30_000],
    )


def graficar_tendencia_arbitraje(df, rango_label):
    df = df.copy()
    df['FECHA_DT'] = pd.to_datetime(df['FECHA_DT']).dt.normalize()
    df = df.sort_values('FECHA_DT').reset_index(drop=True)
    df['TIPO_DIA'] = [_tipo_dia_arbitraje(f) for f in df['FECHA_DT']]
    color_map, label_map = _mapas_leyenda_arbitraje()
    colores = [color_map[t] for t in df['TIPO_DIA']]
    etiquetas = [label_map[t] for t in df['TIPO_DIA']]
    ancho_ms, bargap = _ancho_barras_arbitraje(df)
    yaxis_range = _rango_eje_y_arbitraje(df['ARBITRAJE_MXN'])
    fig = go.Figure()
    fig.add_trace(go.Bar(
        x=df['FECHA_DT'],
        y=df['ARBITRAJE_MXN'],
        width=ancho_ms,
        marker=dict(
            color=colores,
            line=dict(width=0.5, color='rgba(255,255,255,0.6)'),
            cornerradius=4,
        ),
        customdata=etiquetas,
        hovertemplate=(
            '<b>Arbitraje</b><br>%{x|%d/%m/%Y}<br>'
            '%{customdata}<br>$%{y:,.2f}<extra></extra>'
        ),
        showlegend=False,
    ))
    for _, leyenda_nombre, color in LEYENDA_DIA_ARBITRAJE:
        fig.add_trace(go.Bar(
            x=[None],
            y=[None],
            name=leyenda_nombre,
            marker=dict(color=color),
            showlegend=True,
        ))
    fig.update_layout(bargap=bargap, showlegend=True)
    return _aplicar_estilo_grafica_tendencia(
        fig,
        f'Arbitraje diario · {rango_label}',
        'MXN',
        y_tickformat='$,.0f',
        height=624,
        yaxis_range=yaxis_range,
    )
