"""Perfil de carga y demanda rodante."""

from __future__ import annotations

import os

import pandas as pd
import plotly.graph_objects as go

from bess.core.dates import serie_fecha_operativa

from bess.charts.layout import _titulo_y_leyenda_externos
from bess.config import rutas as rutas_mod
from bess.config.subestaciones import (
    etiqueta_medidor_consumo,
    recurso_generacion_subestacion,
    subestacion_por_prefijo,
)
from bess.config.theme import COLORES
from bess.core.consumo import kwh_neto_consumo, usa_consumo_neto

def _kwh_neto_perfil(df: pd.DataFrame, prefijo: str) -> pd.Series | None:
    """kWh netos del ION para el perfil (KWH_NETO o REC−ENT con piso en 0)."""
    if 'KWH_NETO' in df.columns:
        return pd.to_numeric(df['KWH_NETO'], errors='coerce').fillna(0)
    col_rec = f'KWH_REC_{prefijo}'
    col_ent = f'KWH_ENT_{prefijo}'
    if col_rec not in df.columns or col_ent not in df.columns:
        return None
    tmp = df.rename(columns={col_rec: 'KWH_REC', col_ent: 'KWH_ENT'})
    return kwh_neto_consumo(tmp, prefijo)


def _preparar_df_perfil(df: pd.DataFrame, prefijo: str) -> tuple[pd.DataFrame, bool]:
    """Añade KW_REC_ION = KWH_NETO × 12 (potencia neta del medidor, solo IUSA 2)."""
    df = df.copy()
    if not usa_consumo_neto(prefijo):
        return df, False
    kwh_neto = _kwh_neto_perfil(df, prefijo)
    if kwh_neto is None:
        return df, False
    df['KW_REC_ION'] = kwh_neto * 12
    return df, True


def _unir_generacion_perfil(df: pd.DataFrame, prefijo: str) -> pd.DataFrame:
    """Une generación (granja o individual) y calcula KW_GENERACION = KWH_REC × 12."""
    sub = subestacion_por_prefijo(prefijo)
    if not sub:
        return df
    recurso = recurso_generacion_subestacion(sub.id)
    if not recurso:
        return df
    ruta = rutas_mod.ruta_reporte(
        sub.id, f"COMBINADO_POR_MINUTO_{recurso.prefijo_reporte}.csv"
    )
    if not ruta.exists():
        return df
    df_gen = pd.read_csv(ruta, encoding="utf-8-sig")
    if "FECHA_HORA" not in df_gen.columns or "KWH_REC" not in df_gen.columns:
        return df
    df_gen = df_gen[["FECHA_HORA", "KWH_REC"]].rename(columns={"KWH_REC": "KWH_GENERACION"})
    out = df.merge(df_gen, on="FECHA_HORA", how="left")
    out["KWH_GENERACION"] = pd.to_numeric(out["KWH_GENERACION"], errors="coerce").fillna(0)
    out["KW_GENERACION"] = out["KWH_GENERACION"] * 12
    return out


def _unir_granja_perfil(df: pd.DataFrame, prefijo: str) -> pd.DataFrame:
    """Alias legacy — usar _unir_generacion_perfil."""
    return _unir_generacion_perfil(df, prefijo)


def _max_columna(df_plot: pd.DataFrame, columna: str) -> float:
    if columna not in df_plot.columns:
        return 0.0
    return float(pd.to_numeric(df_plot[columna], errors='coerce').fillna(0).max())


def _rango_y_perfil(
    df_plot: pd.DataFrame,
    col_con: str,
    perfil_rec_ent: bool,
) -> list[float] | None:
    """Reserva espacio bajo el eje cero para que la descarga BESS sea visible."""
    pos_cols: list[str] = ['BESS_REC_kW']
    if 'KW_GENERACION' in df_plot.columns:
        pos_cols = ['KW_GENERACION', *pos_cols]
    if perfil_rec_ent:
        pos_cols = ['KW_REC_ION', *pos_cols]
    elif col_con in df_plot.columns:
        pos_cols = [col_con, *pos_cols]

    y_max = max(_max_columna(df_plot, c) for c in pos_cols)
    ent_max = _max_columna(df_plot, 'BESS_ENT_kW')
    if ent_max <= 0:
        return None

    y_min = -ent_max * 1.12
    referencia = y_max if y_max > 0 else ent_max
    y_min = min(y_min, -referencia * 0.18)

    pad_sup = referencia * 0.06 if referencia > 0 else ent_max * 0.06
    pad_inf = abs(y_min) * 0.06
    return [y_min - pad_inf, y_max + pad_sup]


def graficar_perfil(df, prefijo, titulo, *, incluir_generacion: bool = True):
    """Grafica el perfil de carga. Un día: eje X por hora. Varios días: eje X por día (máx. diario)."""
    df = df.copy()
    if 'DATETIME' not in df.columns:
        df['DATETIME'] = pd.to_datetime(df['FECHA_HORA'], format='%d/%m/%Y %H:%M')

    df, perfil_rec_ent = _preparar_df_perfil(df, prefijo)
    if incluir_generacion:
        df = _unir_generacion_perfil(df, prefijo)
    tiene_generacion = incluir_generacion and 'KW_GENERACION' in df.columns
    sub = subestacion_por_prefijo(prefijo)
    recurso_gen = recurso_generacion_subestacion(sub.id) if sub else None
    etiqueta_generacion = (
        f'kW generación ({recurso_gen.etiqueta})' if recurso_gen else 'kW generación'
    )
    etiqueta_ion = etiqueta_medidor_consumo(prefijo)

    col_con = f'IUSA_CON_BESS_{prefijo}_kW'
    if col_con not in df.columns:
        for col in df.columns:
            if 'IUSA_CON_BESS' in col and prefijo in col:
                col_con = col
                break

    multidia = serie_fecha_operativa(df['DATETIME']).nunique() > 1

    if multidia:
        agg_cols = [c for c in ['BESS_REC_kW', 'BESS_ENT_kW'] if c in df.columns]
        if tiene_generacion:
            agg_cols = ['KW_GENERACION'] + agg_cols
        if perfil_rec_ent:
            agg_cols = ['KW_REC_ION'] + agg_cols
        elif col_con in df.columns:
            agg_cols = [col_con] + agg_cols
        df['FECHA_DIA'] = serie_fecha_operativa(df['DATETIME'])
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

    if perfil_rec_ent:
        fig.add_trace(go.Scatter(
            x=x_vals,
            y=df_plot['KW_REC_ION'],
            name=f'kW recibidos ({etiqueta_ion})',
            mode=trace_mode,
            line=dict(color=COLORES['primary'], width=2.5),
            marker=dict(size=marker_size, color=COLORES['primary']),
            fill='tozeroy',
            fillcolor='rgba(26,82,118,0.12)',
        ))
    elif col_con in df_plot.columns:
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

    if tiene_generacion and 'KW_GENERACION' in df_plot.columns:
        fig.add_trace(go.Scatter(
            x=x_vals,
            y=df_plot['KW_GENERACION'],
            name=etiqueta_generacion,
            mode=trace_mode,
            line=dict(color=COLORES['warning'], width=2),
            marker=dict(size=marker_size, color=COLORES['warning']),
            fill='tozeroy',
            fillcolor='rgba(243,156,18,0.12)',
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
        bess_ent = pd.to_numeric(df_plot['BESS_ENT_kW'], errors='coerce').fillna(0)
        descarga_kw = -bess_ent
        fig.add_trace(go.Scatter(
            x=x_vals,
            y=descarga_kw,
            name='Descarga BESS',
            mode=trace_mode,
            line=dict(color=COLORES['descarga'], width=2.5),
            marker=dict(size=marker_size, color=COLORES['descarga']),
            fill='tozeroy',
            fillcolor='rgba(231,76,60,0.22)',
            hovertemplate=(
                '<b>Descarga BESS</b><br>'
                '%{x}<br>'
                '%{customdata:,.1f} kW<extra></extra>'
            ),
            customdata=bess_ent,
        ))

    titulo_grafica = f"{titulo}{titulo_suffix}".strip()
    title_cfg, legend_cfg, margin_t = _titulo_y_leyenda_externos(titulo_grafica)
    y_range = _rango_y_perfil(df_plot, col_con, perfil_rec_ent)
    yaxis_cfg = dict(
        title='Potencia (kW)',
        zeroline=True,
        zerolinecolor='#95a5a6',
        zerolinewidth=1.5,
    )
    if y_range is not None:
        yaxis_cfg['range'] = y_range

    fig.update_layout(
        title=title_cfg,
        xaxis_title=x_title,
        yaxis=yaxis_cfg,
        height=420,
        hovermode='x unified',
        legend=legend_cfg,
        margin=dict(l=52, r=52, t=margin_t, b=40),
    )
    fig.update_xaxes(tickformat=x_tickformat, dtick=x_dtick)

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
