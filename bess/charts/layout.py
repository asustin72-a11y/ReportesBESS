"""Layout común de figuras Plotly (título, leyenda, colores)."""

from __future__ import annotations

from bess.config.theme import COLORES

MARGEN_SUPERIOR_CON_LEYENDA = 132
MARGEN_SUPERIOR_SIN_LEYENDA = 70
LEYENDA_Y_EXTERNA = 0.90


def _titulo_y_leyenda_externos(titulo, font_size=16, show_legend=True):
    """Título fuera del área de trazado y leyenda en el margen superior."""
    title_cfg = dict(
        text=titulo,
        x=0.5,
        xref='container',
        xanchor='center',
        y=1.0,
        yref='container',
        yanchor='top',
        font=dict(size=font_size, color='#1a202c'),
        pad=dict(t=8, b=10),
    )
    legend_cfg = None
    margin_t = MARGEN_SUPERIOR_SIN_LEYENDA
    if show_legend:
        legend_cfg = dict(
            orientation='h',
            yanchor='top',
            y=LEYENDA_Y_EXTERNA,
            yref='container',
            x=0.5,
            xref='container',
            xanchor='center',
            font=dict(size=11, color='#4a5568'),
            bgcolor='rgba(255,255,255,0.85)',
            bordercolor='#e2e8f0',
            borderwidth=1,
            itemclick='toggle',
            itemdoubleclick='toggleothers',
        )
        margin_t = MARGEN_SUPERIOR_CON_LEYENDA
    return title_cfg, legend_cfg, margin_t


def color_periodo(periodo):
    return {'Base': COLORES['base'], 'Intermedio': COLORES['intermedio'], 'Punta': COLORES['punta']}.get(periodo, '#95a5a6')
