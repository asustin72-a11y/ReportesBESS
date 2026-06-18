# styles.py
"""
Configuración de estilos profesionales para gráficas BESS
"""

import matplotlib.pyplot as plt
import matplotlib as mpl
from matplotlib.font_manager import FontProperties
import seaborn as sns

# ========== CONFIGURACIÓN GLOBAL ==========

# Paleta de colores profesional
COLORES_BESS = {
    'primary': '#1a5276',      # Azul profundo
    'secondary': '#2e86c1',    # Azul medio
    'accent': '#1abc9c',       # Turquesa
    'success': '#27ae60',      # Verde
    'warning': '#f39c12',      # Naranja
    'danger': '#e74c3c',       # Rojo
    'purple': '#8e44ad',       # Púrpura
    'gray': '#95a5a6',         # Gris
    'light': '#ecf0f1',        # Gris claro
    'white': '#ffffff',
    
    # Colores para periodos
    'base': '#3498db',         # Azul
    'intermedio': '#f1c40f',   # Amarillo
    'punta': '#e74c3c',        # Rojo
    
    # Colores para BESS
    'carga': '#2ecc71',        # Verde
    'descarga': '#e74c3c',     # Rojo
    'bess': '#1abc9c',         # Turquesa
}

# Estilo base para matplotlib
def configurar_estilo_profesional():
    """Configura el estilo profesional para todas las gráficas"""
    
    # Configurar seaborn para mejor aspecto
    sns.set_theme(style='whitegrid', palette='muted')
    
    # Parámetros de matplotlib
    plt.rcParams.update({
        # Figura
        'figure.figsize': (14, 6),
        'figure.dpi': 150,
        'figure.facecolor': '#f8f9fa',
        
        # Fuentes
        'font.family': 'sans-serif',
        'font.sans-serif': ['Segoe UI', 'Arial', 'Helvetica', 'DejaVu Sans'],
        'font.size': 11,
        
        # Ejes
        'axes.facecolor': '#ffffff',
        'axes.edgecolor': '#e0e0e0',
        'axes.linewidth': 1.2,
        'axes.grid': True,
        'axes.grid.axis': 'y',
        'axes.grid.which': 'major',
        'grid.color': '#e8ecef',
        'grid.linestyle': '--',
        'grid.linewidth': 0.6,
        'grid.alpha': 0.7,
        
        # Ticks
        'xtick.color': '#4a5568',
        'ytick.color': '#4a5568',
        'xtick.labelsize': 10,
        'ytick.labelsize': 10,
        'xtick.direction': 'out',
        'ytick.direction': 'out',
        
        # Títulos y etiquetas
        'axes.titlecolor': '#1a202c',
        'axes.titleweight': 'bold',
        'axes.titlesize': 14,
        'axes.labelcolor': '#2d3748',
        'axes.labelsize': 12,
        'axes.labelweight': 'semibold',
        
        # Leyendas
        'legend.frameon': True,
        'legend.framealpha': 0.95,
        'legend.facecolor': '#ffffff',
        'legend.edgecolor': '#e2e8f0',
        'legend.fontsize': 10,
        'legend.borderpad': 0.8,
        'legend.handlelength': 2.0,
        
        # Líneas
        'lines.linewidth': 2.5,
        'lines.markersize': 5,
        
        # Guardado
        'savefig.dpi': 300,
        'savefig.bbox': 'tight',
        'savefig.facecolor': '#ffffff',
        'savefig.transparent': False,
    })
    
    # Configurar seaborn adicional
    sns.set_context('talk', font_scale=0.9)

def crear_figura(ancho=14, alto=6, titulo=None):
    """Crea una figura con estilo profesional"""
    fig, ax = plt.subplots(figsize=(ancho, alto), facecolor='#f8f9fa')
    ax.set_facecolor('#ffffff')
    
    if titulo:
        ax.set_title(titulo, fontsize=16, fontweight='bold', color='#1a202c', pad=20)
    
    # Estilizar spines
    for spine in ax.spines.values():
        spine.set_color('#e2e8f0')
        spine.set_linewidth(1.5)
    
    return fig, ax

def aplicar_estilo_ax(ax, titulo=None, xlabel=None, ylabel=None):
    """Aplica estilo profesional a un eje existente"""
    ax.set_facecolor('#ffffff')
    
    # Estilizar spines
    for spine in ax.spines.values():
        spine.set_color('#e2e8f0')
        spine.set_linewidth(1.2)
    
    # Configurar grid
    ax.grid(True, axis='y', linestyle='--', alpha=0.6, color='#e8ecef')
    ax.grid(True, axis='x', linestyle='--', alpha=0.3, color='#e8ecef')
    
    # Estilizar ticks
    ax.tick_params(colors='#4a5568', labelsize=10, length=5, width=1.2)
    
    # Estilizar títulos
    if titulo:
        ax.set_title(titulo, fontsize=15, fontweight='bold', color='#1a202c', pad=15)
    if xlabel:
        ax.set_xlabel(xlabel, fontsize=12, fontweight='semibold', color='#2d3748')
    if ylabel:
        ax.set_ylabel(ylabel, fontsize=12, fontweight='semibold', color='#2d3748')
    
    # Estilizar leyenda
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

def colores_periodo(periodo):
    """Retorna el color correspondiente al periodo"""
    colores = {
        'Base': COLORES_BESS['base'],
        'Intermedio': COLORES_BESS['intermedio'],
        'Punta': COLORES_BESS['punta'],
    }
    return colores.get(periodo, '#95a5a6')

def formatear_kw(valor):
    """Formatea valores en kW con separador de miles"""
    return f'{valor:,.1f} kW'

def formatear_kwh(valor):
    """Formatea valores en kWh con separador de miles"""
    return f'{valor:,.0f} kWh'

# Inicializar estilos al importar
configurar_estilo_profesional()