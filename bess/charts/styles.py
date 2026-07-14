"""Estilos compartidos de figuras Plotly."""

from __future__ import annotations

from bess.charts.layout import _titulo_y_leyenda_externos


def _aplicar_estilo_grafica_comparativa(fig, titulo, yaxis_title, y_tickprefix=''):
    """Estilo unificado para barras Con BESS (verde) vs Sin BESS (rojo)."""
    title_cfg, legend_cfg, margin_t = _titulo_y_leyenda_externos(titulo)
    fig.update_layout(
        title=title_cfg,
        barmode='group',
        height=420,
        margin=dict(l=44, r=44, t=margin_t, b=44),
        legend=legend_cfg,
        plot_bgcolor='rgba(0,0,0,0)',
        paper_bgcolor='rgba(0,0,0,0)',
        yaxis=dict(
            title=yaxis_title,
            gridcolor='#eef2f6',
            tickformat=',.0f',
            tickprefix=y_tickprefix,
        ),
        xaxis=dict(domain=[0.0, 1.0]),
    )
    fig.update_xaxes(tickfont=dict(size=11))


def _hex_a_rgba(hex_color, alpha=1.0):
    h = hex_color.lstrip('#')
    r, g, b = int(h[0:2], 16), int(h[2:4], 16), int(h[4:6], 16)
    return f'rgba({r},{g},{b},{alpha})'


def _aplicar_estilo_grafica_tendencia(
    fig, titulo, yaxis_title='', height=520, y_tickformat=None, y_tickprefix='',
    yaxis_range=None, show_legend=True,
):
    """Estilo unificado para gráficas de la pestaña Tendencia."""
    yaxis_cfg = dict(
        title=yaxis_title,
        title_font=dict(size=13, color='#4a5568'),
        tickfont=dict(size=11, color='#4a5568'),
        gridcolor='#eef2f6',
        gridwidth=1,
        zeroline=True,
        zerolinecolor='#dee2e6',
        zerolinewidth=1,
    )
    if y_tickformat is not None:
        yaxis_cfg['tickformat'] = y_tickformat
    if y_tickprefix:
        yaxis_cfg['tickprefix'] = y_tickprefix
    if yaxis_range is not None:
        yaxis_cfg['range'] = yaxis_range

    title_cfg, legend_cfg, margin_t = _titulo_y_leyenda_externos(titulo, show_legend=show_legend)
    layout = dict(
        title=title_cfg,
        height=height,
        margin=dict(l=52, r=28, t=margin_t, b=48),
        hovermode='x unified',
        font=dict(family='Segoe UI, Arial, sans-serif', color='#2d3748', size=12),
        plot_bgcolor='rgba(0,0,0,0)',
        paper_bgcolor='rgba(0,0,0,0)',
        xaxis=dict(
            title='Fecha',
            title_font=dict(size=13, color='#4a5568'),
            tickfont=dict(size=11, color='#4a5568'),
            gridcolor='#eef2f6',
            gridwidth=1,
            showgrid=True,
            zeroline=False,
            tickformat='%d/%m',
        ),
        yaxis=yaxis_cfg,
    )
    if show_legend and legend_cfg is not None:
        layout['legend'] = legend_cfg
    fig.update_layout(**layout)
    return fig
