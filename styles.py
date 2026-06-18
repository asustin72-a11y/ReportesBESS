# styles.py
"""
Configuración de estilos profesionales para gráficas BESS
Versión con soporte para Plotly - CORREGIDA FINAL
"""

import matplotlib.pyplot as plt
import matplotlib as mpl
import seaborn as sns
import plotly.graph_objects as go
import plotly.express as px
from plotly.subplots import make_subplots
import pandas as pd
import numpy as np
import os
from datetime import datetime, timedelta

# ========== CONFIGURACIÓN GLOBAL ==========

# Paleta de colores profesional
COLORES_BESS = {
    'primary': '#1a5276',
    'secondary': '#2e86c1',
    'accent': '#1abc9c',
    'success': '#27ae60',
    'warning': '#f39c12',
    'danger': '#e74c3c',
    'purple': '#8e44ad',
    'gray': '#95a5a6',
    'light': '#ecf0f1',
    'white': '#ffffff',
    'base': '#3498db',
    'intermedio': '#f1c40f',
    'punta': '#e74c3c',
    'carga': '#2ecc71',
    'descarga': '#e74c3c',
    'bess': '#1abc9c',
}

PLOTLY_COLORS = [
    '#1a5276', '#2e86c1', '#1abc9c', '#27ae60', 
    '#f39c12', '#e74c3c', '#8e44ad', '#3498db'
]

# ========== CONFIGURACIÓN DE PLOTLY ==========

def configurar_plotly():
    """Configura el estilo global para Plotly"""
    import plotly.io as pio
    
    template = {
        'layout': {
            'font': {'family': 'Segoe UI, Arial, sans-serif', 'color': '#2d3748'},
            'title': {'font': {'size': 18, 'color': '#1a202c'}, 'x': 0.5},
            'xaxis': {
                'title': {'font': {'size': 14, 'color': '#2d3748'}},
                'tickfont': {'size': 11, 'color': '#4a5568'},
                'gridcolor': '#e8ecef',
                'gridwidth': 1,
                'zerolinecolor': '#e8ecef',
                'zerolinewidth': 1,
            },
            'yaxis': {
                'title': {'font': {'size': 14, 'color': '#2d3748'}},
                'tickfont': {'size': 11, 'color': '#4a5568'},
                'gridcolor': '#e8ecef',
                'gridwidth': 1,
                'zerolinecolor': '#e8ecef',
                'zerolinewidth': 1,
            },
            'legend': {
                'font': {'size': 11, 'color': '#2d3748'},
                'bgcolor': 'rgba(255,255,255,0.9)',
                'bordercolor': '#e2e8f0',
                'borderwidth': 1,
            },
            'plot_bgcolor': '#ffffff',
            'paper_bgcolor': '#f8f9fa',
            'margin': {'l': 60, 'r': 30, 't': 60, 'b': 50},
            'hovermode': 'x unified',
        }
    }
    
    pio.templates['bess'] = template
    pio.templates.default = 'bess'

# ========== FUNCIONES DE ESTILO PARA PLOTLY ==========

def aplicar_estilo_plotly(fig):
    """Aplica estilo profesional a una figura de Plotly"""
    fig.update_layout(
        font=dict(family='Segoe UI, Arial, sans-serif', color='#2d3748'),
        title=dict(font=dict(size=18, color='#1a202c'), x=0.5),
        plot_bgcolor='#ffffff',
        paper_bgcolor='#f8f9fa',
        hovermode='x unified',
        margin=dict(l=60, r=30, t=60, b=50),
        legend=dict(
            font=dict(size=11, color='#2d3748'),
            bgcolor='rgba(255,255,255,0.9)',
            bordercolor='#e2e8f0',
            borderwidth=1,
        )
    )
    
    fig.update_xaxes(
        title_font=dict(size=14, color='#2d3748'),
        tickfont=dict(size=11, color='#4a5568'),
        gridcolor='#e8ecef',
        gridwidth=1,
        zerolinecolor='#e8ecef',
        zerolinewidth=1,
    )
    
    fig.update_yaxes(
        title_font=dict(size=14, color='#2d3748'),
        tickfont=dict(size=11, color='#4a5568'),
        gridcolor='#e8ecef',
        gridwidth=1,
        zerolinecolor='#e8ecef',
        zerolinewidth=1,
    )
    
    return fig

def colores_periodo(periodo):
    colores = {
        'Base': COLORES_BESS['base'],
        'Intermedio': COLORES_BESS['intermedio'],
        'Punta': COLORES_BESS['punta'],
    }
    return colores.get(periodo, '#95a5a6')

def formatear_kw(valor):
    return f'{valor:,.1f} kW'

def formatear_kwh(valor):
    return f'{valor:,.0f} kWh'

# ========== FUNCIONES DE GRÁFICAS PLOTLY ==========

def graficar_comparacion_iusa_plotly(datos_dia, prefijo, fecha_seleccionada):
    """Gráfica de comparación IUSA con Plotly - Interactiva y moderna"""
    
    col_iusa_con = f'IUSA_CON_BESS_{prefijo}_kW'
    col_iusa_sin = f'IUSA_SIN_BESS_{prefijo}_kW'
    
    if col_iusa_con not in datos_dia.columns or col_iusa_sin not in datos_dia.columns:
        fig = go.Figure()
        fig.add_annotation(text="Datos no disponibles", x=0.5, y=0.5, showarrow=False)
        fig.update_layout(height=450)
        return fig
    
    fig = go.Figure()
    
    fig.add_trace(go.Scatter(
        x=datos_dia['DATETIME'],
        y=datos_dia[col_iusa_con],
        name='IUSA Con BESS',
        line=dict(color=COLORES_BESS['primary'], width=3),
        marker=dict(size=4, color=COLORES_BESS['primary']),
        fill='tozeroy',
        fillcolor=f'rgba(26, 82, 118, 0.15)',
        hovertemplate='<b>%{x|%H:%M}</b><br>Potencia: %{y:.1f} kW<extra></extra>'
    ))
    
    fig.add_trace(go.Scatter(
        x=datos_dia['DATETIME'],
        y=datos_dia[col_iusa_sin],
        name='IUSA Sin BESS',
        line=dict(color=COLORES_BESS['warning'], width=3, dash='dash'),
        marker=dict(size=4, color=COLORES_BESS['warning']),
        fill='tozeroy',
        fillcolor=f'rgba(243, 156, 18, 0.12)',
        hovertemplate='<b>%{x|%H:%M}</b><br>Potencia: %{y:.1f} kW<extra></extra>'
    ))
    
    fig.update_layout(
        title=f'Comparación IUSA - {fecha_seleccionada}',
        xaxis_title='Hora del día',
        yaxis_title='Potencia (kW)',
        height=500,
        hovermode='x unified',
    )
    
    fig.update_xaxes(
        tickformat='%H:%M',
        dtick=7200000,
        rangeslider=dict(visible=False),
    )
    
    fig.update_yaxes(
        zeroline=True,
        zerolinecolor='#95a5a6',
        zerolinewidth=1,
    )
    
    return aplicar_estilo_plotly(fig)

def graficar_perfil_carga_plotly(datos_dia, prefijo, fecha_seleccionada):
    """Gráfica de perfil de carga con Plotly - Interactiva"""
    
    col_medidor_rec = f'{prefijo}_REC_kW'
    
    if col_medidor_rec not in datos_dia.columns:
        fig = go.Figure()
        fig.add_annotation(text="Datos no disponibles", x=0.5, y=0.5, showarrow=False)
        fig.update_layout(height=450)
        return fig
    
    fig = go.Figure()
    
    fig.add_trace(go.Scatter(
        x=datos_dia['DATETIME'],
        y=datos_dia[col_medidor_rec],
        name='IUSA Con BESS',
        line=dict(color=COLORES_BESS['primary'], width=3),
        marker=dict(size=4),
        fill='tozeroy',
        fillcolor=f'rgba(26, 82, 118, 0.12)',
        hovertemplate='<b>%{x|%H:%M}</b><br>IUSA: %{y:.1f} kW<extra></extra>'
    ))
    
    fig.add_trace(go.Scatter(
        x=datos_dia['DATETIME'],
        y=datos_dia['BESS_REC_kW'],
        name='Carga BESS',
        line=dict(color=COLORES_BESS['carga'], width=3),
        marker=dict(size=4, symbol='square'),
        fill='tozeroy',
        fillcolor=f'rgba(46, 204, 113, 0.15)',
        hovertemplate='<b>%{x|%H:%M}</b><br>Carga: %{y:.1f} kW<extra></extra>'
    ))
    
    descarga = -datos_dia['BESS_ENT_kW'] if 'BESS_ENT_kW' in datos_dia.columns else np.zeros(len(datos_dia))
    fig.add_trace(go.Scatter(
        x=datos_dia['DATETIME'],
        y=descarga,
        name='Descarga BESS',
        line=dict(color=COLORES_BESS['danger'], width=3),
        marker=dict(size=4, symbol='triangle-up'),
        fill='tozeroy',
        fillcolor=f'rgba(231, 76, 60, 0.15)',
        hovertemplate='<b>%{x|%H:%M}</b><br>Descarga: %{y:.1f} kW<extra></extra>'
    ))
    
    fig.update_layout(
        title=dict(
            text=f'⚡ Perfil de Carga - {fecha_seleccionada}',
            x=0.5,              # Centrado horizontalmente
            xanchor='center',   # Anclaje en el centro
            font=dict(size=18, color='#1a202c')
        ),
        xaxis_title='Hora del día',
        yaxis_title='Potencia (kW)',
        height=500,
        hovermode='x unified',
        legend=dict(
            orientation='h',
            yanchor='bottom',
            y=0.9,
            xanchor='center',
            x=0.5
        )
    )
    
    fig.update_xaxes(
        tickformat='%H:%M',
        dtick=7200000,
    )
    
    fig.update_yaxes(
        zeroline=True,
        zerolinecolor='#95a5a6',
        zerolinewidth=1,
    )
    
    return aplicar_estilo_plotly(fig)

def graficar_arbitraje_periodos_plotly(arbitraje_data, fecha_seleccionada):
    """Gráfica de barras interactiva para arbitraje por periodo"""
    
    periodos = ['Base', 'Intermedio', 'Punta']
    valores = [arbitraje_data['arbitraje'].get(p, 0) for p in periodos]
    
    colores_rgba = [
        f'rgba(52, 152, 219, 0.85)',
        f'rgba(241, 196, 15, 0.85)',
        f'rgba(231, 76, 60, 0.85)'
    ]
    
    fig = go.Figure()
    
    fig.add_trace(go.Bar(
        x=periodos,
        y=valores,
        text=[f'${v:,.0f}' for v in valores],
        textposition='outside',
        marker=dict(
            color=colores_rgba,
            line=dict(color='white', width=2)
        ),
        hovertemplate='<b>%{x}</b><br>Arbitraje: $%{y:,.0f}<extra></extra>'
    ))
    
    fig.add_hline(y=0, line=dict(color='#4a5568', width=1, dash='dash'))
    
    fig.update_layout(
        title=f'💹 Arbitraje por Periodo - {fecha_seleccionada}',
        xaxis_title='Periodo',
        yaxis_title='Arbitraje ($)',
        height=400,
        showlegend=False,
    )
    
    fig.update_yaxes(
        zeroline=True,
        zerolinecolor='#4a5568',
        zerolinewidth=1,
    )
    
    return aplicar_estilo_plotly(fig)

def graficar_consumo_diario_plotly(df_dia, prefijo, fecha_seleccionada):
    """Gráfica de carga vs descarga BESS con estilo uniforme - MEJORADA"""
    
    if 'PERIODO' not in df_dia.columns:
        fig = go.Figure()
        fig.add_annotation(text="Datos no disponibles", x=0.5, y=0.5, showarrow=False)
        fig.update_layout(height=450)
        return fig
    
    consumo = df_dia.groupby('PERIODO').agg({
        'KWH_REC_BESS': 'sum',
        'KWH_ENT_BESS': 'sum'
    }).reset_index()
    
    periodos = ['Base', 'Intermedio', 'Punta']
    carga = [consumo[consumo['PERIODO'] == p]['KWH_REC_BESS'].sum() for p in periodos]
    descarga = [consumo[consumo['PERIODO'] == p]['KWH_ENT_BESS'].sum() for p in periodos]
    
    fig = go.Figure()
    
    # Barras de carga - con estilo similar a IUSA
    fig.add_trace(go.Bar(
        x=periodos,
        y=carga,
        name='Carga BESS',
        marker=dict(
            color=COLORES_BESS['carga'],
            line=dict(color='white', width=2)
        ),
        text=[f'{v:,.0f}' for v in carga],
        textposition='outside',
        textfont=dict(size=11, color='#2d3748'),
        hovertemplate='<b>%{x}</b><br>Carga: %{y:,.1f} kWh<extra></extra>'
    ))
    
    # Barras de descarga - con estilo similar a IUSA
    fig.add_trace(go.Bar(
        x=periodos,
        y=descarga,
        name='Descarga BESS',
        marker=dict(
            color=COLORES_BESS['danger'],
            line=dict(color='white', width=2)
        ),
        text=[f'{v:,.0f}' for v in descarga],
        textposition='outside',
        textfont=dict(size=11, color='#2d3748'),
        hovertemplate='<b>%{x}</b><br>Descarga: %{y:,.1f} kWh<extra></extra>'
    ))
    
    # Configurar layout con el mismo estilo que Comparación IUSA
    fig.update_layout(
        title=dict(
            text=f'⚡ Carga vs Descarga BESS - {fecha_seleccionada}',
            x=0.5,              # Centrado horizontalmente
            xanchor='center',   # Anclaje en el centro
            font=dict(size=18, color='#1a202c')
        ),
        xaxis_title='Periodo',
        yaxis_title='Energía (kWh)',
        height=500,
        barmode='group',
        bargap=0.15,
        bargroupgap=0.1,
        hovermode='x unified',
        legend=dict(
            orientation='h',
            yanchor='bottom',
            y=0.9,
            xanchor='center',
            x=0.5,
            font=dict(size=11, color='#2d3748'),
            bgcolor='rgba(255,255,255,0.9)',
            bordercolor='#e2e8f0',
            borderwidth=1,
        )
    )
    
    # Configurar ejes con el mismo estilo
    fig.update_xaxes(
        title_font=dict(size=14, color='#2d3748'),
        tickfont=dict(size=11, color='#4a5568'),
        gridcolor='#e8ecef',
        gridwidth=1,
        zerolinecolor='#e8ecef',
        zerolinewidth=1,
    )
    
    fig.update_yaxes(
        title_font=dict(size=14, color='#2d3748'),
        tickfont=dict(size=11, color='#4a5568'),
        gridcolor='#e8ecef',
        gridwidth=1,
        zeroline=True,
        zerolinecolor='#95a5a6',
        zerolinewidth=1,
    )
    
    return aplicar_estilo_plotly(fig)

def graficar_tendencia_mensual_plotly(prefijo, directorio_reportes=None):
    """Gráfica de tendencia mensual interactiva"""
    
    if directorio_reportes is None:
        base_dir = os.path.dirname(os.path.abspath(__file__))
        directorio_reportes = os.path.join(base_dir, 'data', 'ArchivosReporte')
    
    ruta_dia = os.path.join(directorio_reportes, f'ENERGIA_{prefijo}_POR_DIA.csv')
    
    if not os.path.exists(ruta_dia):
        fig = go.Figure()
        fig.add_annotation(text="Datos no disponibles", x=0.5, y=0.5, showarrow=False)
        fig.update_layout(height=450)
        return fig
    
    df_dia = pd.read_csv(ruta_dia)
    df_dia['FECHA_DT'] = pd.to_datetime(df_dia['FECHA'], format='%d/%m/%Y')
    df_dia = df_dia.sort_values('FECHA_DT')
    df_dia['CONSUMO_TOTAL'] = df_dia['BASE_REC'] + df_dia['INTERMEDIO_REC'] + df_dia['PUNTA_REC']
    
    fig = go.Figure()
    
    fig.add_trace(go.Scatter(
        x=df_dia['FECHA_DT'],
        y=df_dia['CONSUMO_TOTAL'],
        name='Consumo Total',
        line=dict(color=COLORES_BESS['primary'], width=3),
        fill='tozeroy',
        fillcolor=f'rgba(26, 82, 118, 0.15)',
        marker=dict(size=6, color=COLORES_BESS['primary']),
        hovertemplate='<b>%{x|%d/%m}</b><br>Consumo: %{y:,.0f} kWh<extra></extra>'
    ))
    
    if len(df_dia) > 7:
        media_movil = df_dia['CONSUMO_TOTAL'].rolling(window=7, min_periods=3).mean()
        fig.add_trace(go.Scatter(
            x=df_dia['FECHA_DT'],
            y=media_movil,
            name='Tendencia (7 días)',
            line=dict(color=COLORES_BESS['accent'], width=2.5, dash='dash'),
            hovertemplate='<b>%{x|%d/%m}</b><br>Tendencia: %{y:,.0f} kWh<extra></extra>'
        ))
    
    fig.update_layout(
        title=f'📈 Tendencia de Consumo Diario - {prefijo}',
        xaxis_title='Fecha',
        yaxis_title='Energía (kWh)',
        height=450,
        hovermode='x unified',
    )
    
    fig.update_xaxes(
        tickformat='%d/%m',
        dtick=86400000 * 3,
    )
    
    fig.update_yaxes(
        zeroline=True,
        zerolinecolor='#95a5a6',
        zerolinewidth=1,
    )
    
    return aplicar_estilo_plotly(fig)

def graficar_dispersion_plotly(df_dia):
    """Gráfica de dispersión interactiva: Carga vs Descarga"""
    
    if 'PERIODO' not in df_dia.columns:
        fig = go.Figure()
        fig.add_annotation(text="Datos no disponibles", x=0.5, y=0.5, showarrow=False)
        fig.update_layout(height=450)
        return fig
    
    df_hora = df_dia.groupby('HORA').agg({
        'BESS_REC_kW': 'mean',
        'BESS_ENT_kW': 'mean'
    }).reset_index()
    
    fig = go.Figure()
    
    fig.add_trace(go.Scatter(
        x=df_hora['BESS_REC_kW'],
        y=df_hora['BESS_ENT_kW'],
        mode='markers',
        marker=dict(
            size=15,
            color=df_hora['HORA'],
            colorscale='Plasma',
            showscale=True,
            colorbar=dict(title='Hora'),
            line=dict(color='white', width=2)
        ),
        text=[f'Hora: {h}:00' for h in df_hora['HORA']],
        hovertemplate='<b>%{text}</b><br>Carga: %{x:.1f} kW<br>Descarga: %{y:.1f} kW<extra></extra>'
    ))
    
    max_val = max(df_hora['BESS_REC_kW'].max(), df_hora['BESS_ENT_kW'].max()) * 1.1
    fig.add_trace(go.Scatter(
        x=[0, max_val],
        y=[0, max_val],
        mode='lines',
        line=dict(color='#95a5a6', width=2, dash='dash'),
        name='Carga = Descarga',
        hovertemplate=None
    ))
    
    fig.update_layout(
        title='🔄 Relación Carga/Descarga por Hora',
        xaxis_title='Carga BESS (kW)',
        yaxis_title='Descarga BESS (kW)',
        height=450,
        hovermode='closest',
    )
    
    return aplicar_estilo_plotly(fig)

def graficar_sankey_plotly(df_dia):
    """Diagrama de Sankey interactivo para flujo de energía"""
    
    if 'PERIODO' not in df_dia.columns:
        fig = go.Figure()
        fig.add_annotation(text="Datos no disponibles", x=0.5, y=0.5, showarrow=False)
        fig.update_layout(height=500)
        return fig
    
    flujos = {}
    for periodo in ['Base', 'Intermedio', 'Punta']:
        df_periodo = df_dia[df_dia['PERIODO'] == periodo]
        carga = df_periodo['KWH_REC_BESS'].sum()
        descarga = df_periodo['KWH_ENT_BESS'].sum()
        flujos[periodo] = {'carga': carga, 'descarga': descarga}
    
    labels = ['Red Eléctrica'] + list(flujos.keys()) + ['Consumo', 'Pérdidas']
    
    source = [0, 0, 0]
    target = [1, 2, 3]
    values = [flujos['Base']['carga'], flujos['Intermedio']['carga'], flujos['Punta']['carga']]
    
    source.extend([1, 2, 3])
    target.extend([4, 4, 4])
    values.extend([flujos['Base']['descarga'], flujos['Intermedio']['descarga'], flujos['Punta']['descarga']])
    
    source.extend([1, 2, 3])
    target.extend([5, 5, 5])
    values.extend([
        max(0, flujos['Base']['carga'] - flujos['Base']['descarga']),
        max(0, flujos['Intermedio']['carga'] - flujos['Intermedio']['descarga']),
        max(0, flujos['Punta']['carga'] - flujos['Punta']['descarga'])
    ])
    
    colores = ['#3498db', '#2ecc71', '#f1c40f', '#e74c3c', '#1abc9c', '#95a5a6']
    
    fig = go.Figure(data=[go.Sankey(
        node=dict(
            pad=20,
            thickness=30,
            line=dict(color='white', width=2),
            label=labels,
            color=colores,
        ),
        link=dict(
            source=source,
            target=target,
            value=values,
            color=[f'rgba(52,152,219,0.4)'] * 3 + [f'rgba(46,204,113,0.4)'] * 3 + [f'rgba(231,76,60,0.3)'] * 3,
        )
    )])
    
    fig.update_layout(
        title='🌊 Flujo de Energía BESS',
        height=500,
        font=dict(size=12),
    )
    
    return aplicar_estilo_plotly(fig)

# ========== FUNCIONES DE ESTILO PARA MATPLOTLIB ==========

def configurar_estilo_profesional():
    plt.rcParams.update({
        'figure.figsize': (14, 6),
        'figure.dpi': 150,
        'figure.facecolor': '#f8f9fa',
        'font.family': 'sans-serif',
        'font.sans-serif': ['Segoe UI', 'Arial', 'Helvetica', 'DejaVu Sans'],
        'font.size': 11,
        'axes.facecolor': '#ffffff',
        'axes.edgecolor': '#e0e0e0',
        'axes.linewidth': 1.2,
        'axes.grid': True,
        'axes.grid.axis': 'y',
        'grid.color': '#e8ecef',
        'grid.linestyle': '--',
        'grid.linewidth': 0.6,
        'xtick.color': '#4a5568',
        'ytick.color': '#4a5568',
        'xtick.labelsize': 10,
        'ytick.labelsize': 10,
        'axes.titlecolor': '#1a202c',
        'axes.titleweight': 'bold',
        'axes.titlesize': 14,
        'axes.labelcolor': '#2d3748',
        'axes.labelsize': 12,
        'axes.labelweight': 'semibold',
        'legend.frameon': True,
        'legend.framealpha': 0.95,
        'legend.facecolor': '#ffffff',
        'legend.edgecolor': '#e2e8f0',
        'legend.fontsize': 10,
        'lines.linewidth': 2.5,
        'savefig.dpi': 300,
        'savefig.bbox': 'tight',
    })
    sns.set_theme(style='whitegrid', palette='muted')

def crear_figura(ancho=14, alto=6):
    fig, ax = plt.subplots(figsize=(ancho, alto), facecolor='#f8f9fa')
    ax.set_facecolor('#ffffff')
    return fig, ax

def aplicar_estilo_ax(ax, titulo=None, xlabel=None, ylabel=None):
    ax.set_facecolor('#ffffff')
    
    for spine in ax.spines.values():
        spine.set_color('#e2e8f0')
        spine.set_linewidth(1.2)
    
    ax.grid(True, axis='y', linestyle='--', alpha=0.6, color='#e8ecef')
    ax.grid(True, axis='x', linestyle='--', alpha=0.3, color='#e8ecef')
    ax.tick_params(colors='#4a5568', labelsize=10, length=5, width=1.2)
    
    if titulo:
        ax.set_title(titulo, fontsize=15, fontweight='bold', color='#1a202c', pad=15)
    if xlabel:
        ax.set_xlabel(xlabel, fontsize=12, fontweight='semibold', color='#2d3748')
    if ylabel:
        ax.set_ylabel(ylabel, fontsize=12, fontweight='semibold', color='#2d3748')
    
    if ax.get_legend():
        ax.legend(
            frameon=True,
            facecolor='#ffffff',
            edgecolor='#e2e8f0',
            fontsize=10,
            loc='best',
            borderpad=0.8,
            handlelength=2.5,
        )
    
    return ax

# Inicializar estilos
configurar_estilo_profesional()
configurar_plotly()