# app_plotly.py - Versión corregida

"""
BESS - Sistema de Procesamiento y Reportes - Web App
Versión simplificada con selector de fechas básico
"""

import streamlit as st
import pandas as pd
import numpy as np
import os
from datetime import datetime, timedelta
import warnings
import io
import hashlib
import base64
import html
import shutil
import subprocess
import sys
import plotly.graph_objects as go
import plotly.express as px
from decimal import Decimal, ROUND_HALF_UP
import streamlit.components.v1 as components

# ========== CONFIGURACIÓN INICIAL ==========
st.set_page_config(
    page_title="BESS - Sistema de Energía",
    page_icon="⚡",
    layout="wide",
    initial_sidebar_state="collapsed",
)

warnings.filterwarnings('ignore')

# ========== CONSTANTES ==========
DIRECTORIO_BASE = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'data')
DIRECTORIO_FUENTE = os.path.join(DIRECTORIO_BASE, 'ArchivosFuente')
DIRECTORIO_PROCESADOS = os.path.join(DIRECTORIO_BASE, 'ArchivosProcesados')
DIRECTORIO_REPORTES = os.path.join(DIRECTORIO_BASE, 'ArchivosReporte')
DIRECTORIO_REPORTES_DIARIOS = os.path.join(DIRECTORIO_BASE, 'ReportesDiarios')
DIRECTORIO_TARIFAS = os.path.join(DIRECTORIO_BASE, 'Tarifas')
ARCHIVO_TARIFAS = 'Tarifas_2026.csv'
TIPOS_TARIFA = [
    'Base', 'Intermedio', 'Punta', 'Capacidad',
    'CargoFijo', 'Suministro', 'Distribucion', 'ServiciosAuxiliares',
    'Transmision', 'CENACE',
]

for dir_path in [DIRECTORIO_BASE, DIRECTORIO_FUENTE, DIRECTORIO_PROCESADOS,
                 DIRECTORIO_REPORTES, DIRECTORIO_REPORTES_DIARIOS, DIRECTORIO_TARIFAS]:
    os.makedirs(dir_path, exist_ok=True)

# ========== COLORES ==========
COLORES = {
    'primary': '#1a5276',
    'secondary': '#2e86c1',
    'success': '#27ae60',
    'warning': '#f39c12',
    'danger': '#e74c3c',
    'base': '#3498db',
    'intermedio': '#f1c40f',
    'punta': '#e74c3c',
    'carga': '#2ecc71',
    'descarga': '#e74c3c',
}

MARGEN_SUPERIOR_CON_LEYENDA = 118
MARGEN_SUPERIOR_SIN_LEYENDA = 62
LEYENDA_Y_EXTERNA = 0.945

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
        pad=dict(t=8, b=4),
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
        )
        margin_t = MARGEN_SUPERIOR_CON_LEYENDA
    return title_cfg, legend_cfg, margin_t

def color_periodo(periodo):
    return {'Base': COLORES['base'], 'Intermedio': COLORES['intermedio'], 'Punta': COLORES['punta']}.get(periodo, '#95a5a6')

PERIODO_BG = {
    'Base': 'rgba(52, 152, 219, 0.14)',
    'Intermedio': 'rgba(241, 196, 15, 0.18)',
    'Punta': 'rgba(231, 76, 60, 0.14)',
}

def _a_num(val):
    v = pd.to_numeric(val, errors='coerce')
    return 0.0 if pd.isna(v) else float(v)

def sumar_energia(val):
    """Suma kWh conservando decimales."""
    if isinstance(val, pd.Series):
        return float(pd.to_numeric(val, errors='coerce').fillna(0).sum())
    if isinstance(val, pd.DataFrame):
        return float(pd.to_numeric(val, errors='coerce').fillna(0).sum().sum())
    if isinstance(val, (list, tuple, np.ndarray)):
        return float(np.nansum(pd.to_numeric(val, errors='coerce')))
    return _a_num(val)

def _redondear_half_up(val, decimales=0):
    """Redondeo ≥0.5 hacia arriba, <0.5 hacia abajo."""
    quantum = Decimal('1') if decimales == 0 else Decimal(f'0.{"0" * (decimales - 1)}1')
    return Decimal(str(_a_num(val))).quantize(quantum, rounding=ROUND_HALF_UP)

def redondear_kwh(val):
    """kWh: redondeo al entero más cercano (≥0.5 arriba, <0.5 abajo)."""
    return int(_redondear_half_up(val, 0))

def fmt_kwh(val):
    """Formatea kWh para mostrar (redondeo al entero más cercano)."""
    return f"{redondear_kwh(val):,}"

def redondear_mxn_energia(val):
    """Costo de energía (MXN): redondeo a 2 decimales (≥0.5 arriba)."""
    return float(_redondear_half_up(val, 2))

def kwh_para_calculo(val):
    """kWh redondeados usados en cálculos monetarios de energía."""
    return redondear_kwh(val)

def redondear_arriba_kw(val):
    """Demanda / capacidad (kW): redondeo hacia arriba."""
    return int(np.ceil(_a_num(val)))

def redondear_arriba_mxn(val):
    """Costo de capacidad (MXN): redondeo hacia arriba con 2 decimales."""
    return np.ceil(_a_num(val) * 100) / 100

def section_header(titulo, descripcion='', compact=False):
    cls = 'section-title-sm' if compact else 'section-title'
    html = f'<p class="{cls}">{titulo}</p>'
    if descripcion:
        html += f'<p class="section-desc">{descripcion}</p>'
    st.markdown(html, unsafe_allow_html=True)

def render_selector_fecha_unica(titulo, descripcion, label, fecha_def, fecha_min, fecha_max, key, metric_label=None, metric_fn=None):
    """Panel compacto con un solo date_input y métrica auxiliar opcional."""
    with st.container(border=True):
        st.markdown('<span class="panel-fecha-unica-anchor" aria-hidden="true"></span>', unsafe_allow_html=True)
        section_header(titulo, descripcion, compact=True)
        if metric_label and metric_fn:
            col_fecha, col_info = st.columns([3, 1])
            with col_fecha:
                fecha = st.date_input(
                    label,
                    value=fecha_def,
                    min_value=fecha_min,
                    max_value=fecha_max,
                    key=key,
                )
            with col_info:
                metric_compact(metric_label, metric_fn(fecha))
        else:
            fecha = st.date_input(
                label,
                value=fecha_def,
                min_value=fecha_min,
                max_value=fecha_max,
                key=key,
            )
    return fecha

def metric_compact(label, value):
    st.markdown(
        f'<div class="metric-compact"><div class="label">{label}</div>'
        f'<div class="value">{value}</div></div>',
        unsafe_allow_html=True,
    )

def html_tarifas_sidebar(tarifas, mes):
    items = [
        ('Base', f"${tarifas.get('Base', {}).get(mes, 0):.4f}"),
        ('Intermedio', f"${tarifas.get('Intermedio', {}).get(mes, 0):.4f}"),
        ('Punta', f"${tarifas.get('Punta', {}).get(mes, 0):.4f}"),
        ('Capacidad', f"${tarifas.get('Capacidad', {}).get(mes, 0):,.2f}"),
    ]
    celdas = ''.join(
        f'<div class="sidebar-tarifa-item"><div class="label">{lbl}</div>'
        f'<div class="value">{val}</div></div>'
        for lbl, val in items
    )
    return f'<div class="sidebar-tarifas-grid">{celdas}</div>'

def estado_datos_sin_bess(prefijo):
    """Estado consolidado de columnas sin BESS."""
    return {
        'energia': energia_diaria_tiene_sin_bess(prefijo),
        'demanda': acumulados_tiene_demanda_sin_bess(prefijo),
    }

def mostrar_aviso_sin_bess(estado):
    msgs = []
    if not estado['energia']:
        msgs.append('energía diaria (`ENERGIA_*_POR_DIA.csv`)')
    if not estado['demanda']:
        msgs.append('demanda en acumulados (`ACUMULADOS_*.csv`)')
    if msgs:
        st.info(
            'Faltan datos sin BESS en: ' + ' y '.join(msgs) + '. '
            'Vuelve a procesar los datos desde el panel de administración.'
        )
        return True
    return False

def obtener_logo_html(width=110):
    logo_path = os.path.join(DIRECTORIO_BASE, 'Logo IUSASOL.png')
    if not os.path.exists(logo_path):
        logo_path = os.path.join(DIRECTORIO_BASE, 'LogoIUSASOL.png')
    if not os.path.exists(logo_path):
        return ""
    with open(logo_path, 'rb') as logo_file:
        logo_b64 = base64.b64encode(logo_file.read()).decode()
    mime = 'image/png' if logo_path.lower().endswith('.png') else 'image/jpeg'
    return (
        f'<img src="data:{mime};base64,{logo_b64}" width="{width}" '
        f'alt="IUSASOL" style="display:block;" />'
    )

def obtener_logo_cfe_html(width=200):
    """Logo CFE embebido en base64 para el recibo simulado."""
    candidatos = [
        os.path.join(DIRECTORIO_BASE, 'Comisión_Federal_de_Electricidad_(logo).jpg'),
        os.path.join(DIRECTORIO_BASE, 'Comision_Federal_de_Electricidad_(logo).jpg'),
    ]
    for logo_path in candidatos:
        if not os.path.exists(logo_path):
            continue
        with open(logo_path, 'rb') as logo_file:
            logo_b64 = base64.b64encode(logo_file.read()).decode()
        ext = os.path.splitext(logo_path)[1].lower()
        mime = 'image/jpeg' if ext in ('.jpg', '.jpeg') else 'image/png'
        return (
            f'<img class="cfe-logo-img" src="data:{mime};base64,{logo_b64}" '
            f'width="{width}" alt="Comisión Federal de Electricidad" />'
        )
    return ''

def render_barra_superior(es_admin):
    """Logo, título y cierre de sesión."""
    logo_html = obtener_logo_html(288)
    usuario = st.session_state.get('usuario', '')
    rol_nombre = USUARIOS.get(usuario, {}).get('nombre', usuario)
    rol_tipo = 'Administrador' if es_admin else 'Visualizador'
    logo_block = (
        f'<div style="flex-shrink:0;background:white;border-radius:8px;padding:4px 8px;">{logo_html}</div>'
        if logo_html else ''
    )
    c1, c2 = st.columns([6, 1])
    with c1:
        st.markdown(f"""
        <div class="app-header">
            {logo_block}
            <div>
                <h1 class="app-header-title">BESS · Sistema de Energía</h1>
                <p class="app-header-sub">{rol_tipo}: {rol_nombre}</p>
            </div>
        </div>
        """, unsafe_allow_html=True)
    with c2:
        st.markdown('<div style="height:18px"></div>', unsafe_allow_html=True)
        if st.button("Cerrar sesión", use_container_width=True, key="btn_logout"):
            logout()

def render_selector_rango(df, prefijo, key_suffix, medidor=None):
    """Selector de rango de fechas y resumen del periodo."""
    if 'DATETIME' not in df.columns:
        df = df.copy()
        df['DATETIME'] = pd.to_datetime(df['FECHA_HORA'], format='%d/%m/%Y %H:%M')

    fecha_min = df['DATETIME'].min().date()
    fecha_max = df['DATETIME'].max().date()
    fecha_def = datetime.now().date() - timedelta(days=1)
    fecha_def = max(fecha_min, min(fecha_def, fecha_max))

    if medidor:
        st.markdown(
            f'<p class="contexto-medidor">Medidor activo: <b>{medidor}</b></p>',
            unsafe_allow_html=True,
        )
    col1, col2, col3 = st.columns([2, 2, 1])
    with col1:
        fecha_inicio = st.date_input(
            "Desde",
            fecha_def,
            min_value=fecha_min,
            max_value=fecha_max,
            key=f"finicio_{prefijo}_{key_suffix}",
        )
    with col2:
        fecha_fin = st.date_input(
            "Hasta",
            fecha_def,
            min_value=fecha_min,
            max_value=fecha_max,
            key=f"ffin_{prefijo}_{key_suffix}",
        )
    with col3:
        dias = (fecha_fin - fecha_inicio).days + 1
        st.metric("Días", dias)

    fecha_inicio_dt = datetime.combine(fecha_inicio, datetime.min.time())
    fecha_fin_dt = datetime.combine(fecha_fin, datetime.max.time())
    mask = (df['DATETIME'] >= fecha_inicio_dt) & (df['DATETIME'] <= fecha_fin_dt)
    df_filtrado = df[mask].copy()

    st.markdown(f"""
    <div class="fecha-resumen">
        <b>{len(df_filtrado):,}</b> registros ·
        <b>{len(df_filtrado['FECHA_HORA'].unique()):,}</b> horas ·
        del <b>{fecha_inicio.strftime('%d/%m/%Y')}</b> al <b>{fecha_fin.strftime('%d/%m/%Y')}</b>
    </div>
    """, unsafe_allow_html=True)

    return fecha_inicio, fecha_fin, df_filtrado

def estilizar_tabla_energia(df_tabla):
    styler = df_tabla.style.set_properties(
        subset=['Periodo'],
        **{'font-weight': '500', 'text-align': 'left'}
    )
    for col in ['Base', 'Intermedio', 'Punta']:
        styler = styler.set_properties(
            subset=[col],
            **{'background-color': PERIODO_BG[col], 'text-align': 'right'}
        )
    styler = styler.set_properties(
        subset=['Total'],
        **{'background-color': 'rgba(26, 82, 118, 0.10)', 'font-weight': '600', 'text-align': 'right'}
    )
    idx_arb = df_tabla[df_tabla['Periodo'].str.contains('Arbitraje', na=False)].index
    if len(idx_arb) > 0:
        styler = styler.set_properties(
            subset=pd.IndexSlice[idx_arb[0], :],
            **{'font-weight': '700', 'background-color': '#e8f4f8', 'border-top': '2px solid #1a5276'}
        )
    styler = styler.set_table_styles([
        {'selector': 'thead th', 'props': [
            ('background-color', '#2c3e50'), ('color', 'white'),
            ('font-weight', '700'), ('text-align', 'center'), ('padding', '8px')
        ]},
        {'selector': 'thead th.col_heading.level0.col1', 'props': [
            ('background-color', COLORES['base']), ('color', 'white')
        ]},
        {'selector': 'thead th.col_heading.level0.col2', 'props': [
            ('background-color', '#d4ac0d'), ('color', 'white')
        ]},
        {'selector': 'thead th.col_heading.level0.col3', 'props': [
            ('background-color', COLORES['punta']), ('color', 'white')
        ]},
        {'selector': 'thead th.col_heading.level0.col4', 'props': [
            ('background-color', '#1a5276'), ('color', 'white')
        ]},
    ], overwrite=False)
    return styler

def tarjeta_arbitraje_html(periodo, valor, es_total=False):
    if es_total:
        color = COLORES['primary']
        bg = '#e8f4f8'
        label = 'TOTAL'
    else:
        color = color_periodo(periodo)
        bg = PERIODO_BG.get(periodo, '#f8fafc')
        label = periodo
    clase_valor = 'positivo' if valor >= 0 else 'negativo'
    return f"""
    <div class="arbitraje-card" style="border-left:4px solid {color}; background:{bg};">
        <div class="periodo" style="color:{color};">{label}</div>
        <div class="valor {clase_valor}">${valor:,.2f}</div>
    </div>
    """

def _etiqueta_capacidad_cfe(res):
    """Texto de capacidad kW según criterio CFE aplicado."""
    if res['criterio_aplicado'] == 'punta':
        return f"{res['capacidad_kw']:,} kW · demanda punta"
    return f"{res['capacidad_kw']:,} kW · DemandaCalculadaCFE"

def html_comparacion_capacidad(res_con, res_sin, precio_cap, ahorro):
    capacidad_con = res_con['costo_mxn']
    capacidad_sin = res_sin['costo_mxn']
    pct_ahorro = (ahorro / capacidad_sin * 100) if capacidad_sin > 0 else 0
    reduccion_kw = res_sin['capacidad_kw'] - res_con['capacidad_kw']
    clase_centro = '' if ahorro >= 0 else 'negativo'
    etiqueta_ahorro = 'Ahorro mensual' if ahorro >= 0 else 'Incremento'
    return f"""
    <div class="cap-tarifa">
        Tarifa capacidad: <b>${precio_cap:,.2f}</b> ·
        Capacidad CFE = min(demanda punta, DemandaCalculadaCFE) × tarifa
    </div>
    <div class="capacidad-comparacion">
        <div class="cap-bloque cap-sin">
            <div class="cap-etiqueta">Sin BESS</div>
            <div class="cap-demanda">{_etiqueta_capacidad_cfe(res_sin)}</div>
            <div class="cap-costo">${capacidad_sin:,.2f}</div>
        </div>
        <div class="cap-centro {clase_centro}">
            <div class="cap-ahorro-valor">${abs(ahorro):,.2f}</div>
            <div class="cap-ahorro-label">{etiqueta_ahorro} ({pct_ahorro:+.1f}%)</div>
            <div class="cap-ahorro-sub">{reduccion_kw:+,} kW de capacidad CFE</div>
        </div>
        <div class="cap-bloque cap-con">
            <div class="cap-etiqueta">Con BESS</div>
            <div class="cap-demanda">{_etiqueta_capacidad_cfe(res_con)}</div>
            <div class="cap-costo">${capacidad_con:,.2f}</div>
        </div>
    </div>
    """

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

PERIODOS_ENERGIA = [
    ('base', 'Base'),
    ('intermedio', 'Intermedio'),
    ('punta', 'Punta'),
]

_COLUMNAS_ENERGIA_CON = {
    'base': 'BASE_REC',
    'intermedio': 'INTERMEDIO_REC',
    'punta': 'PUNTA_REC',
}
_COLUMNAS_ENERGIA_SIN = {
    'base': 'BASE_REC_SIN_BESS',
    'intermedio': 'INTERMEDIO_REC_SIN_BESS',
    'punta': 'PUNTA_REC_SIN_BESS',
}

def calcular_costo_energia_rango(fecha_inicio, fecha_fin, prefijo, con_bess=True, tarifas=None):
    """kWh por periodo en un rango de fechas × tarifa → costo MXN."""
    if tarifas is None:
        tarifas = cargar_tarifas()
    columnas = _COLUMNAS_ENERGIA_CON if con_bess else _COLUMNAS_ENERGIA_SIN
    ruta = os.path.join(DIRECTORIO_REPORTES, f'ENERGIA_{prefijo}_POR_DIA.csv')
    if not os.path.exists(ruta):
        return None
    df = pd.read_csv(ruta)
    df['FECHA_DT'] = pd.to_datetime(df['FECHA'], format='%d/%m/%Y')
    mask = (df['FECHA_DT'].dt.date >= fecha_inicio) & (df['FECHA_DT'].dt.date <= fecha_fin)
    df_r = df[mask]
    if df_r.empty:
        return None

    por_periodo_raw = {}
    for clave, col in columnas.items():
        if col not in df_r.columns:
            return None
        por_periodo_raw[clave] = sumar_energia(pd.to_numeric(df_r[col], errors='coerce').fillna(0))

    mes = fecha_fin.month
    tarifa_keys = {'base': 'Base', 'intermedio': 'Intermedio', 'punta': 'Punta'}
    por_periodo = {}
    for clave, _ in PERIODOS_ENERGIA:
        kwh = kwh_para_calculo(por_periodo_raw.get(clave, 0))
        precio = tarifas.get(tarifa_keys[clave], {}).get(mes, 0)
        por_periodo[clave] = {
            'kwh': kwh,
            'precio': precio,
            'costo_mxn': redondear_mxn_energia(kwh * precio),
        }
    total_mxn = redondear_mxn_energia(sum(p['costo_mxn'] for p in por_periodo.values()))
    kwh_activo = sum(por_periodo_raw.get(clave, 0) for clave, _ in PERIODOS_ENERGIA)
    return {
        'por_periodo': por_periodo,
        'total_kwh': sum(p['kwh'] for p in por_periodo.values()),
        'kwh_activo': kwh_activo,
        'total_mxn': total_mxn,
        'dias_rango': (fecha_fin - fecha_inicio).days + 1,
    }

def calcular_costo_energia_mes(fecha, prefijo, con_bess=True, tarifas=None):
    """Acumulado del mes: kWh por periodo × tarifa → costo MXN."""
    fecha_inicio = fecha.replace(day=1)
    res = calcular_costo_energia_rango(fecha_inicio, fecha, prefijo, con_bess, tarifas)
    if res is None:
        return None
    res['dias_mes'] = dias_transcurridos_mes(fecha)
    return res

def calcular_arbitraje_desde_costos(res_sin, res_con):
    """Ahorro/arbitraje = costo sin BESS − costo con BESS (misma regla que Energía y costos)."""
    arbitraje = {}
    for clave, _ in PERIODOS_ENERGIA:
        arbitraje[clave] = (
            res_sin['por_periodo'][clave]['costo_mxn']
            - res_con['por_periodo'][clave]['costo_mxn']
        )
    return {
        'base': arbitraje['base'],
        'intermedio': arbitraje['intermedio'],
        'punta': arbitraje['punta'],
        'total': res_sin['total_mxn'] - res_con['total_mxn'],
    }

def _calcular_arbitraje_bess_periodo(carga_base, carga_intermedio, carga_punta,
                                     descarga_base, descarga_intermedio, descarga_punta,
                                     precio_base, precio_intermedio, precio_punta):
    """Arbitraje operativo BESS: (descarga − carga) × tarifa por periodo."""
    arbitraje_base = redondear_mxn_energia(
        (kwh_para_calculo(descarga_base) - kwh_para_calculo(carga_base)) * precio_base
    )
    arbitraje_intermedio = redondear_mxn_energia(
        (kwh_para_calculo(descarga_intermedio) - kwh_para_calculo(carga_intermedio)) * precio_intermedio
    )
    arbitraje_punta = redondear_mxn_energia(
        (kwh_para_calculo(descarga_punta) - kwh_para_calculo(carga_punta)) * precio_punta
    )
    arbitraje_total = redondear_mxn_energia(
        arbitraje_base + arbitraje_intermedio + arbitraje_punta
    )
    return arbitraje_base, arbitraje_intermedio, arbitraje_punta, arbitraje_total

def _html_lineas_costo_periodo(res):
    return ''.join(
        f'<div class="cap-demanda">'
        f'{res["por_periodo"][clave]["kwh"]:,} kWh {lbl} · '
        f'${res["por_periodo"][clave]["costo_mxn"]:,.2f}'
        f'</div>'
        for clave, lbl in PERIODOS_ENERGIA
    )

def _texto_tarifas_mes(tarifas, mes_num):
    partes = [
        f'{lbl} ${tarifas.get(lbl, {}).get(mes_num, 0):,.4f}'
        for _, lbl in PERIODOS_ENERGIA
    ]
    precio_cap = tarifas.get('Capacidad', {}).get(mes_num, 0)
    partes.append(f'Capacidad ${precio_cap:,.2f}')
    return ' · '.join(partes)

def html_comparacion_costo_energia(res_con, res_sin, tarifas, mes_num):
    tarifas_txt = _texto_tarifas_mes(tarifas, mes_num)
    ahorro = res_sin['total_mxn'] - res_con['total_mxn']
    pct_ahorro = (ahorro / res_sin['total_mxn'] * 100) if res_sin['total_mxn'] > 0 else 0
    diff_kwh = res_sin['total_kwh'] - res_con['total_kwh']
    clase_centro = '' if ahorro >= 0 else 'negativo'
    etiqueta_ahorro = 'Ahorro acumulado' if ahorro >= 0 else 'Incremento'
    return f"""
    <div class="cap-tarifa">
        Tarifas del mes: {tarifas_txt}<br>
        Acumulado del mes al día seleccionado · kWh × tarifa por periodo
    </div>
    <div class="capacidad-comparacion">
        <div class="cap-bloque cap-sin">
            <div class="cap-etiqueta">Sin BESS</div>
            {_html_lineas_costo_periodo(res_sin)}
            <div class="cap-costo">${res_sin['total_mxn']:,.2f}</div>
            <div class="cap-ahorro-sub">{res_sin['total_kwh']:,} kWh total</div>
        </div>
        <div class="cap-centro {clase_centro}">
            <div class="cap-ahorro-valor">${abs(ahorro):,.2f}</div>
            <div class="cap-ahorro-label">{etiqueta_ahorro} ({pct_ahorro:+.1f}%)</div>
            <div class="cap-ahorro-sub">{diff_kwh:+,} kWh vs sin BESS</div>
        </div>
        <div class="cap-bloque cap-con">
            <div class="cap-etiqueta">Con BESS</div>
            {_html_lineas_costo_periodo(res_con)}
            <div class="cap-costo">${res_con['total_mxn']:,.2f}</div>
            <div class="cap-ahorro-sub">{res_con['total_kwh']:,} kWh total</div>
        </div>
    </div>
    """

def construir_tabla_costo_energia(res_con, res_sin):
    filas = []
    for clave, lbl in PERIODOS_ENERGIA:
        pc = res_con['por_periodo'][clave]
        ps = res_sin['por_periodo'][clave]
        filas.append({
            'Periodo': lbl,
            'kWh con BESS': f"{pc['kwh']:,}",
            'kWh sin BESS': f"{ps['kwh']:,}",
            'Tarifa ($/kWh)': f"${pc['precio']:.4f}",
            'Costo con BESS (MXN)': f"${pc['costo_mxn']:,.2f}",
            'Costo sin BESS (MXN)': f"${ps['costo_mxn']:,.2f}",
            'Diferencia (MXN)': f"${ps['costo_mxn'] - pc['costo_mxn']:,.2f}",
        })
    filas.append({
        'Periodo': 'Total',
        'kWh con BESS': f"{res_con['total_kwh']:,}",
        'kWh sin BESS': f"{res_sin['total_kwh']:,}",
        'Tarifa ($/kWh)': '—',
        'Costo con BESS (MXN)': f"${res_con['total_mxn']:,.2f}",
        'Costo sin BESS (MXN)': f"${res_sin['total_mxn']:,.2f}",
        'Diferencia (MXN)': f"${res_sin['total_mxn'] - res_con['total_mxn']:,.2f}",
    })
    return pd.DataFrame(filas)

def construir_tabla_recibo_energia(res_energia):
    """Desglose de energía para un escenario (con o sin BESS)."""
    filas = []
    for clave, lbl in PERIODOS_ENERGIA:
        p = res_energia['por_periodo'][clave]
        filas.append({
            'Concepto': f'Energía {lbl}',
            'kWh': f"{p['kwh']:,}",
            'Tarifa ($/kWh)': f"${p['precio']:.4f}",
            'Importe (MXN)': f"${p['costo_mxn']:,.2f}",
        })
    filas.append({
        'Concepto': 'Subtotal energía',
        'kWh': f"{res_energia['total_kwh']:,}",
        'Tarifa ($/kWh)': '—',
        'Importe (MXN)': f"${res_energia['total_mxn']:,.2f}",
    })
    return pd.DataFrame(filas)

def construir_tabla_recibo_completo(res_energia, res_cfe):
    """Tabla unificada del recibo: energía + capacidad CFE + total."""
    filas = construir_tabla_recibo_energia(res_energia).to_dict('records')
    if res_cfe is not None:
        lbl_criterio = (
            'Demanda punta'
            if res_cfe['criterio_aplicado'] == 'punta'
            else 'DemandaCalculadaCFE'
        )
        filas.append({
            'Concepto': 'Capacidad CFE',
            'kWh': (
                f"{res_cfe['capacidad_kw']:,} kW · {lbl_criterio} · "
                f"${res_cfe['precio_cap']:,.2f}/kW"
            ),
            'Tarifa ($/kWh)': '—',
            'Importe (MXN)': f"${res_cfe['costo_mxn']:,.2f}",
        })
    total = res_energia['total_mxn'] + (res_cfe['costo_mxn'] if res_cfe else 0)
    filas.append({
        'Concepto': 'Total recibo',
        'kWh': '—',
        'Tarifa ($/kWh)': '—',
        'Importe (MXN)': f"${total:,.2f}",
    })
    return pd.DataFrame(filas), total

MESES_CFE = (
    'ENE', 'FEB', 'MAR', 'ABR', 'MAY', 'JUN',
    'JUL', 'AGO', 'SEP', 'OCT', 'NOV', 'DIC',
)

DATOS_CLIENTE_RECIBO = {
    'ION': {
        'razon_social': 'INDUSTRIAS UNIDAS SA DE CV',
        'direccion': (
            'CARR PANAMERICANA MEXICO QUERE',
            'JOCOTITLAN C FZA',
            'C.P.50700',
            'JOCOTITLAN,MEX.',
        ),
        'no_servicio': '306140811981',
        'cuenta': '84DG41H108350020',
        'rmu': '50700 14-07-31 IUN -390731 001 CFE',
        'tarifa': 'DIST',
        'multiplicador': '44000',
        'no_hilos': '3',
        'no_medidor': '764DXX',
        'carga_conectada_kw': 31000,
        'demanda_contratada_kw': 31000,
    },
    'BANCO': {
        'razon_social': 'INDUSTRIAS UNIDAS SA DE CV',
        'direccion': (
            'CARR PANAMERICANA MEXICO QUERE',
            'JOCOTITLAN C FZA',
            'C.P.50700',
            'JOCOTITLAN,MEX.',
        ),
        'no_servicio': '—',
        'cuenta': '—',
        'rmu': '—',
        'tarifa': 'DIST',
        'multiplicador': '—',
        'no_hilos': '3',
        'no_medidor': 'BANCO',
        'carga_conectada_kw': None,
        'demanda_contratada_kw': None,
    },
}

_UNIDADES_ES = (
    ('millones', 1_000_000),
    ('mil', 1_000),
    ('', 1),
)
_DECENAS_ES = (
    'diez', 'once', 'doce', 'trece', 'catorce', 'quince', 'dieciséis', 'diecisiete',
    'dieciocho', 'diecinueve',
)
_UNIDADES_LETRAS = (
    '', 'uno', 'dos', 'tres', 'cuatro', 'cinco', 'seis', 'siete', 'ocho', 'nueve',
)
_DECENAS_LETRAS = (
    '', '', 'veinte', 'treinta', 'cuarenta', 'cincuenta', 'sesenta', 'setenta',
    'ochenta', 'noventa',
)
_CENTENAS_LETRAS = (
    '', 'ciento', 'doscientos', 'trescientos', 'cuatrocientos', 'quinientos',
    'seiscientos', 'setecientos', 'ochocientos', 'novecientos',
)

def _fmt_fecha_cfe(fecha):
    return f'{fecha.day:02d} {MESES_CFE[fecha.month - 1]} {fecha.year % 100:02d}'

def _periodo_facturado_cfe(fecha):
    inicio = fecha.replace(day=1)
    return f'{_fmt_fecha_cfe(inicio)}-{_fmt_fecha_cfe(fecha)}'

def _fmt_mxn_entero(val):
    return f'${int(round(_a_num(val))):,}'

def _fmt_mxn_decimal(val):
    return f'${_a_num(val):,.2f}'

def _fmt_cargo_fp_recibo(val):
    """Penalización positiva; bonificación negativa en el desglose."""
    monto = _a_num(val)
    if monto < 0:
        return f'-${abs(monto):,.2f}'
    return _fmt_mxn_decimal(monto)

def _numero_menor_1000_a_letras(n):
    n = int(n)
    if n == 0:
        return ''
    if n == 100:
        return 'cien'
    if n < 10:
        return _UNIDADES_LETRAS[n]
    if n < 20:
        return _DECENAS_ES[n - 10]
    if n < 100:
        d, u = divmod(n, 10)
        if u == 0:
            return _DECENAS_LETRAS[d]
        if d == 2:
            return f'veinti{_UNIDADES_LETRAS[u]}'
        return f'{_DECENAS_LETRAS[d]} y {_UNIDADES_LETRAS[u]}'
    c, resto = divmod(n, 100)
    pref = _CENTENAS_LETRAS[c]
    if resto == 0:
        return pref
    return f'{pref} {_numero_menor_1000_a_letras(resto)}'

def _entero_a_letras_es(n):
    n = int(n)
    if n == 0:
        return 'cero'
    partes = []
    for nombre, valor in _UNIDADES_ES:
        if n >= valor:
            cant = n // valor
            n %= valor
            texto = _numero_menor_1000_a_letras(cant)
            if nombre == 'millones' and cant == 1:
                texto = 'un millón'
            elif nombre == 'millones':
                texto = f'{texto} millones'
            elif nombre == 'mil' and cant == 1:
                texto = 'mil'
            elif nombre == 'mil':
                texto = f'{texto} mil'
            partes.append(texto)
    return ' '.join(partes)

def _monto_a_letras_mxn(val):
    entero = int(round(_a_num(val)))
    letras = _entero_a_letras_es(entero).upper()
    return f'({letras} PESOS M.N.)'

def obtener_demanda_kw_periodo_mes(fecha, prefijo, con_bess=True):
    """Demanda máxima acumulada del mes por periodo (ACUMULADOS_*.csv)."""
    fila = _fila_por_fecha(_cargar_acumulados(prefijo), fecha)
    if fila is None:
        return None
    tipo = 'CON_BESS' if con_bess else 'SIN_BESS'
    resultado = {}
    for clave in ('base', 'intermedio', 'punta'):
        col = f'{clave.upper()}_DEM_{tipo}_MAX'
        kw = pd.to_numeric(fila.get(col, 0), errors='coerce')
        resultado[clave] = redondear_arriba_kw(0 if pd.isna(kw) else kw)
    resultado['kw_max'] = max(resultado.values())
    return resultado

def obtener_kvarh_mes(fecha, prefijo):
    """kVArh acumulados del mes al día indicado (reportes BESS, sin truncar)."""
    fila = _fila_por_fecha(_cargar_acumulados(prefijo), fecha)
    if fila is not None and 'KVARH_ACUM' in fila.index:
        val = pd.to_numeric(fila.get('KVARH_ACUM', 0), errors='coerce')
        if not pd.isna(val):
            return float(val)

    ruta_dia = os.path.join(DIRECTORIO_REPORTES, f'ENERGIA_{prefijo}_POR_DIA.csv')
    if os.path.exists(ruta_dia):
        df = pd.read_csv(ruta_dia)
        if 'KVARH' in df.columns:
            df['FECHA_DT'] = pd.to_datetime(df['FECHA'], format='%d/%m/%Y')
            df_r = _filtrar_mes_hasta_fecha(df, fecha, 'FECHA_DT')
            if not df_r.empty:
                return float(pd.to_numeric(df_r['KVARH'], errors='coerce').fillna(0).sum())

    from bess.config.subestaciones import medidor_consumo_por_prefijo

    med = medidor_consumo_por_prefijo(prefijo)
    if not med:
        return None
    ruta = os.path.join(DIRECTORIO_PROCESADOS, med.consumo_filtrado)
    if not os.path.exists(ruta):
        ruta = os.path.join(DIRECTORIO_PROCESADOS, med.consumo_csv)
        if not os.path.exists(ruta):
            return None
    df = pd.read_csv(ruta)
    if 'Fecha' not in df.columns:
        return None
    df['FECHA_DT'] = pd.to_datetime(df['Fecha'])
    df_r = _filtrar_mes_hasta_fecha(df, fecha, 'FECHA_DT')
    if df_r.empty:
        return None
    from bess_core import _columnas_kvarh_prefijo, _normalizar_columnas_kvarh
    cols = [c for c in _columnas_kvarh_prefijo(prefijo) if c in df_r.columns]
    if not cols:
        return None
    df_r = _normalizar_columnas_kvarh(df_r.copy())
    return float(df_r[cols].sum().sum())

def calcular_factor_potencia_pct(kwh_activo, kvarh_total):
    """
    Factor de potencia % = kWh activos / sqrt(kWh² + kVArh²) × 100.
    kWh activos: suma base + intermedio + punta.
    kVArh: suma de reactivos del medidor (ION=Q1, BANCO=Q1+Q4).
    """
    kwh_activo = _a_num(kwh_activo)
    kvarh_total = _a_num(kvarh_total)
    if kwh_activo <= 0:
        return 0.0
    return round(kwh_activo / ((kwh_activo ** 2 + kvarh_total ** 2) ** 0.5) * 100, 2)

def calcular_factor_potencia_recibo(res_energia, kvarh_total):
    """FP del recibo: energía activa (3 periodos) + reactivos acumulados."""
    if kvarh_total is None:
        return None
    return calcular_factor_potencia_pct(
        _kwh_activo_tres_periodos(res_energia), kvarh_total
    )

FP_UMBRAL_PCT = 97.0
FP_MAX_BONIFICACION = 0.025   # tope 2.5 %
FP_MAX_PENALIZACION = 1.20    # tope 120 %

def _coef_cargo_fp_redondeado(coef):
    return float(Decimal(str(coef)).quantize(Decimal('0.001'), rounding=ROUND_HALF_UP))

def calcular_cargo_fp(factor_potencia_pct, cargo_fijo, energia, capacidad):
    """
    Cargo FP por factor de potencia (base = Cargo Fijo + Energía + Capacidad):
    - FP < 97%: penalización min((3/5)×((97/FP)−1), 120%) × base.
    - FP > 97%: bonificación −min((1/4)×(1−(97/FP)), 2.5%) × base.
    - FP = 97% o sin dato: 0.
    Coeficiente redondeado a 3 decimales en ambos casos.
    """
    if factor_potencia_pct is None:
        return 0.0
    fp = _a_num(factor_potencia_pct)
    if fp <= 0:
        return 0.0
    base = _a_num(cargo_fijo) + _a_num(energia) + _a_num(capacidad)
    if fp < FP_UMBRAL_PCT:
        coef = min((3 / 5) * ((97 / fp) - 1), FP_MAX_PENALIZACION)
        coef = _coef_cargo_fp_redondeado(coef)
        return redondear_mxn_energia(coef * base)
    if fp > FP_UMBRAL_PCT:
        coef = min((1 / 4) * (1 - (97 / fp)), FP_MAX_BONIFICACION)
        coef = _coef_cargo_fp_redondeado(coef)
        return redondear_mxn_energia(-coef * base)
    return 0.0

def _tarifa_mes(tarifas, mes, *nombres):
    """Obtiene tarifa del mes probando varios nombres de fila (CSV)."""
    for nombre in nombres:
        vals = tarifas.get(nombre)
        if vals is not None:
            return float(vals.get(mes, 0) or 0)
    return 0.0

def _kwh_activo_tres_periodos(res_energia):
    kwh = res_energia.get('kwh_activo')
    if kwh is not None:
        return float(kwh)
    return float(sum(
        res_energia['por_periodo'][clave]['kwh']
        for clave, _ in PERIODOS_ENERGIA
    ))

def _precio_generacion_neto(tarifas, mes, periodo_tarifa, precio_cenace, precio_transmision, precio_scnmem):
    """Tarifa de generación neta = tarifa del periodo − CENACE − Transmisión − ServiciosAuxiliares."""
    tarifa = _tarifa_mes(tarifas, mes, periodo_tarifa)
    return tarifa - precio_cenace - precio_transmision - precio_scnmem

def _celda_generacion_mem(kwh, precio_neto):
    return _celda_mem(redondear_mxn_energia(kwh * precio_neto), precio_kwh=precio_neto)

def _celda_mem(importe, precio_kwh=0.0, precio_kw=0.0):
    return {
        'precio_kwh': precio_kwh,
        'precio_kw': precio_kw,
        'importe': importe,
    }

def construir_datos_recibo_cfe(fecha, prefijo, con_bess, res_energia, res_cfe, tarifas):
    """Arma el diccionario de datos para el layout tipo recibo CFE."""
    cliente = DATOS_CLIENTE_RECIBO.get(prefijo, DATOS_CLIENTE_RECIBO['ION'])
    escenario = 'Con BESS' if con_bess else 'Sin BESS'
    pp = res_energia['por_periodo']
    demanda = obtener_demanda_kw_periodo_mes(fecha, prefijo, con_bess=con_bess)
    kvarh = obtener_kvarh_mes(fecha, prefijo)
    fp_pct = calcular_factor_potencia_recibo(res_energia, kvarh)

    costo_cap = res_cfe['costo_mxn'] if res_cfe else 0.0
    precio_cap = res_cfe['precio_cap'] if res_cfe else 0.0
    capacidad_kw = res_cfe['capacidad_kw'] if res_cfe else 0
    mes = fecha.month
    kwh_activo = _kwh_activo_tres_periodos(res_energia)

    tarifa_suministro = _tarifa_mes(tarifas, mes, 'Suministro')
    tarifa_cargo_fijo = _tarifa_mes(tarifas, mes, 'CargoFijo', 'Cargo Fijo')
    tarifa_distribucion = _tarifa_mes(tarifas, mes, 'Distribucion', 'Distribución')
    precio_transmision = _tarifa_mes(tarifas, mes, 'Transmision', 'Transmisión')
    precio_cenace = _tarifa_mes(tarifas, mes, 'CENACE')
    precio_scnmem = _tarifa_mes(tarifas, mes, 'ServiciosAuxiliares', 'SCnMEM')
    importe_transmision = redondear_mxn_energia(kwh_activo * precio_transmision)
    importe_cenace = redondear_mxn_energia(kwh_activo * precio_cenace)
    importe_scnmem = redondear_mxn_energia(kwh_activo * precio_scnmem)

    precio_gen_base = _precio_generacion_neto(
        tarifas, mes, 'Base', precio_cenace, precio_transmision, precio_scnmem
    )
    precio_gen_inter = _precio_generacion_neto(
        tarifas, mes, 'Intermedio', precio_cenace, precio_transmision, precio_scnmem
    )
    precio_gen_punta = _precio_generacion_neto(
        tarifas, mes, 'Punta', precio_cenace, precio_transmision, precio_scnmem
    )

    mem = {
        'Suministro': _celda_mem(tarifa_suministro),
        'Distribución': _celda_mem(tarifa_distribucion),
        'Transmisión': _celda_mem(importe_transmision, precio_kwh=precio_transmision),
        'CENACE': _celda_mem(importe_cenace, precio_kwh=precio_cenace),
        'Generación B': _celda_generacion_mem(pp['base']['kwh'], precio_gen_base),
        'Generación I': _celda_generacion_mem(pp['intermedio']['kwh'], precio_gen_inter),
        'Generación P': _celda_generacion_mem(pp['punta']['kwh'], precio_gen_punta),
        'Capacidad': _celda_mem(costo_cap, precio_kw=precio_cap),
        'SCnMEM(1)': _celda_mem(importe_scnmem, precio_kwh=precio_scnmem),
    }
    total_mem = sum(v['importe'] for v in mem.values())

    importe_energia = res_energia['total_mxn']
    importe_cargo_fp = calcular_cargo_fp(
        fp_pct, tarifa_cargo_fijo, importe_energia, costo_cap
    )
    subtotal = importe_energia + costo_cap + tarifa_cargo_fijo + importe_cargo_fp
    iva = redondear_mxn_energia(subtotal * 0.16)
    total_pagar = redondear_mxn_energia(subtotal + iva)

    fecha_limite = fecha + timedelta(days=18)
    corte_partir = fecha + timedelta(days=1)

    return {
        'escenario': escenario,
        'cliente': cliente,
        'fecha_corte': fecha,
        'periodo_facturado': _periodo_facturado_cfe(fecha),
        'fecha_limite_pago': _fmt_fecha_cfe(fecha_limite),
        'corte_partir': _fmt_fecha_cfe(corte_partir),
        'dias_mes': res_energia['dias_mes'],
        'kwh': {
            'base': redondear_kwh(pp['base']['kwh']),
            'intermedio': redondear_kwh(pp['intermedio']['kwh']),
            'punta': redondear_kwh(pp['punta']['kwh']),
            'total': redondear_kwh(res_energia['total_kwh']),
        },
        'kw': demanda or {'base': 0, 'intermedio': 0, 'punta': 0, 'kw_max': 0},
        'kvarh': kvarh,
        'factor_potencia_pct': fp_pct,
        'mem': mem,
        'total_mem': total_mem,
        'desglose': {
            'cargo_fijo': tarifa_cargo_fijo,
            'energia': importe_energia,
            'capacidad': costo_cap,
            'cargo_fp': importe_cargo_fp,
            'subtotal': subtotal,
            'iva': iva,
            'total': total_pagar,
        },
        'capacidad_kw': capacidad_kw,
        'capacidad_criterio': (
            'Demanda punta'
            if res_cfe and res_cfe['criterio_aplicado'] == 'punta'
            else 'DemandaCalculadaCFE'
        ) if res_cfe else '—',
    }

RECIBO_ANCHO_REF_PX = 920
RECIBO_FACTOR_ANCHO = 0.80
RECIBO_FACTOR_ALTURA = 1.20
RECIBO_LOGO_ANCHO_REF = 210
RECIBO_FACTOR_LOGO = 0.98

def _recibo_logo_ancho_px():
    return max(1, round(RECIBO_LOGO_ANCHO_REF * RECIBO_FACTOR_ANCHO * RECIBO_FACTOR_LOGO))

def _recibo_px(base, factor):
    return max(1, round(base * factor))

def _css_recibo_cfe(for_pdf=False):
    """Estilos del recibo con valores fijos (compatibles con pantalla y PDF)."""
    v = RECIBO_FACTOR_ALTURA
    h = RECIBO_FACTOR_ANCHO
    pv = lambda n: _recibo_px(n, v)
    ph = lambda n: _recibo_px(n, h)
    fs = lambda n: max(6, n - 1) if for_pdf else n
    max_w = round(RECIBO_ANCHO_REF_PX * h)
    logo_w = _recibo_logo_ancho_px()
    lh = round(1.25 * v, 2)
    lh_sm = round(1.3 * v, 2)
    return f"""
        .cfe-recibo-wrap {{
            max-width: {max_w}px;
            margin: 0 auto 16px;
        }}
        .cfe-recibo {{
            font-family: Arial, Helvetica, sans-serif;
            color: #000;
            background: #fff;
            border: 2px solid #000;
            box-shadow: 0 2px 10px rgba(0, 0, 0, 0.12);
            font-size: {fs(11)}px;
            line-height: {lh};
        }}
        .cfe-layout-table {{
            width: 100%;
            border-collapse: collapse;
        }}
        .cfe-recibo-sim {{
            background: #f5f5f5;
            color: #444;
            text-align: center;
            font-size: {fs(10)}px;
            font-weight: 700;
            letter-spacing: 0.06em;
            text-transform: uppercase;
            padding: {pv(5)}px {ph(8)}px;
            border-bottom: 3px solid #008250;
        }}
        .cfe-recibo-top td {{
            vertical-align: top;
            padding: {pv(10)}px {ph(12)}px {pv(8)}px;
            border-bottom: 1px solid #000;
        }}
        .cfe-emisor td {{
            vertical-align: top;
            padding: 0;
        }}
        .cfe-emisor .cfe-logo-block {{
            width: {logo_w}px;
            vertical-align: middle;
            text-align: center;
            padding-right: {ph(10)}px;
        }}
        .cfe-logo-inner {{
            text-align: center;
        }}
        .cfe-logo-img {{
            display: inline-block;
            height: auto;
            max-width: {logo_w}px;
            vertical-align: middle;
        }}
        .cfe-emisor-nombre, .cfe-receptor-nombre {{
            font-weight: 700;
            font-size: {fs(12)}px;
            margin-bottom: {pv(3)}px;
            color: #008250;
        }}
        .cfe-emisor-dir, .cfe-receptor-dir, .cfe-emisor-rfc {{
            color: #111;
            font-size: {fs(10)}px;
            line-height: {lh_sm};
        }}
        .cfe-receptor {{
            text-align: right;
            border-left: 1px solid #ccc;
            padding-left: {ph(10)}px;
        }}
        .cfe-receptor-etq {{
            font-size: {fs(9)}px;
            font-weight: 700;
            letter-spacing: 0.05em;
            color: #555;
            margin-bottom: {pv(4)}px;
        }}
        .cfe-servicio td {{
            width: 20%;
            padding: {pv(5)}px {ph(7)}px;
            border: 1px solid #000;
            vertical-align: top;
            min-height: {pv(34)}px;
        }}
        .cfe-servicio-item span {{
            display: block;
            color: #333;
            font-size: {fs(8)}px;
            font-weight: 700;
            letter-spacing: 0.03em;
            text-transform: uppercase;
            margin-bottom: {pv(2)}px;
        }}
        .cfe-servicio-item b {{
            font-size: {fs(11)}px;
            color: #000;
            font-weight: 700;
        }}
        .cfe-periodo {{
            padding: {pv(6)}px {ph(12)}px;
            background: #e8f5ee;
            border-bottom: 2px solid #008250;
            font-size: {fs(11)}px;
        }}
        .cfe-periodo-etq {{
            font-weight: 700;
            letter-spacing: 0.03em;
        }}
        .cfe-periodo-dias {{
            color: #444;
            font-size: {fs(10)}px;
            margin-left: 4px;
        }}
        .cfe-total-wrap td {{
            vertical-align: middle;
            padding: {pv(10)}px {ph(12)}px;
            border-bottom: 2px solid #000;
        }}
        .cfe-total-label {{
            font-weight: 800;
            font-size: {fs(14)}px;
            letter-spacing: 0.04em;
            color: #000;
        }}
        .cfe-total-monto-box {{
            border: 2px solid #000;
            padding: {pv(8)}px {ph(14)}px;
            background: #fff;
            text-align: center;
            width: {ph(220)}px;
        }}
        .cfe-total-monto {{
            font-size: {fs(26)}px;
            font-weight: 800;
            color: #000;
            white-space: nowrap;
            letter-spacing: 0.02em;
        }}
        .cfe-total-letras {{
            margin-top: {pv(4)}px;
            font-size: {fs(9)}px;
            color: #333;
            line-height: {lh};
            max-width: 95%;
        }}
        .cfe-body td {{
            vertical-align: top;
            padding: {pv(8)}px {ph(10)}px;
            border-bottom: 1px solid #000;
        }}
        .cfe-consumo-panel {{
            width: 31%;
            border-right: 1px solid #000;
            background: #fff;
        }}
        .cfe-mem-panel {{
            width: 69%;
            background: #fff;
        }}
        .cfe-panel-title {{
            font-weight: 800;
            font-size: {fs(10)}px;
            text-transform: uppercase;
            color: #008250;
            margin-bottom: {pv(6)}px;
            letter-spacing: 0.04em;
            border-bottom: 1px solid #008250;
            padding-bottom: {pv(3)}px;
        }}
        .cfe-mini-table, .cfe-mem-table, .cfe-desglose-table {{
            width: 100%;
            border-collapse: collapse;
            font-size: {fs(10)}px;
        }}
        .cfe-mini-table th, .cfe-mem-table th {{
            background: #ececec;
            color: #000;
            padding: {pv(4)}px {ph(5)}px;
            text-align: center;
            font-size: {fs(9)}px;
            font-weight: 700;
            border: 1px solid #000;
        }}
        .cfe-mini-table td, .cfe-mem-table td, .cfe-desglose-table td {{
            border: 1px solid #000;
            padding: {pv(3)}px {ph(5)}px;
            vertical-align: middle;
        }}
        .cfe-mini-table td:first-child, .cfe-desglose-table td:first-child {{
            font-weight: 600;
        }}
        .cfe-mem-table td:first-child {{ font-weight: 600; }}
        .cfe-mem-row:nth-child(even) td {{ background: #fafafa; }}
        .cfe-mem-total td {{
            background: #e8f5ee;
            font-weight: 800;
        }}
        .cfe-mem-nota {{
            margin-top: {pv(5)}px;
            font-size: {fs(8)}px;
            color: #555;
            line-height: {lh};
            font-style: italic;
        }}
        .cfe-desglose {{
            padding: {pv(8)}px {ph(12)}px {pv(10)}px;
            background: #fff;
        }}
        .cfe-desglose-table td:last-child {{ text-align: right; width: 36%; }}
        .cfe-desglose-total td {{
            background: #e8f5ee;
            font-weight: 800;
            border-top: 2px solid #008250;
        }}
        .cfe-footnote {{
            padding: {pv(6)}px {ph(12)}px {pv(8)}px;
            font-size: {fs(8)}px;
            color: #555;
            background: #f5f5f5;
            border-top: 1px solid #ccc;
            text-align: center;
        }}
        .cfe-recibo .num {{ text-align: right; white-space: nowrap; }}
"""

def _html_servicio_celda(etiqueta, valor):
    return f'<td class="cfe-servicio-item"><span>{etiqueta}</span><b>{valor}</b></td>'

def _html_fila_mem(concepto, celda, es_total=False):
    cls = 'cfe-mem-row cfe-mem-total' if es_total else 'cfe-mem-row'
    pkwh = '—' if celda['precio_kwh'] == 0 else f"{celda['precio_kwh']:.4f}"
    pkw = '—' if celda['precio_kw'] == 0 else f"{celda['precio_kw']:,.2f}"
    imp = f"{celda['importe']:,.2f}"
    return (
        f'<tr class="{cls}">'
        f'<td>{concepto}</td>'
        f'<td class="num">{pkwh}</td>'
        f'<td class="num">{pkw}</td>'
        f'<td class="num">{imp}</td>'
        f'</tr>'
    )

def render_html_recibo_cfe(datos):
    """HTML del recibo con layout similar al aviso CFE."""
    c = datos['cliente']
    dir_html = ''.join(f'<div>{linea}</div>' for linea in c['direccion'])
    carga = (
        f"{c['carga_conectada_kw']:,}"
        if c.get('carga_conectada_kw') is not None else '—'
    )
    demanda_cta = (
        f"{c['demanda_contratada_kw']:,}"
        if c.get('demanda_contratada_kw') is not None else '—'
    )
    kwh = datos['kwh']
    kw = datos['kw']
    d = datos['desglose']
    kvarh_txt = f"{int(round(datos['kvarh'])):,}" if datos['kvarh'] is not None else '—'
    fp_txt = f"{datos['factor_potencia_pct']:.2f}" if datos['factor_potencia_pct'] is not None else '—'

    filas_mem = ''.join(
        _html_fila_mem(nombre, celda)
        for nombre, celda in datos['mem'].items()
    )
    total_mem = _celda_mem(datos['total_mem'])
    filas_mem += _html_fila_mem('TOTAL', total_mem, es_total=True)
    logo_cfe = obtener_logo_cfe_html(_recibo_logo_ancho_px())
    campos_servicio = [
        ('NO. DE SERVICIO', c['no_servicio']),
        ('CUENTA', c['cuenta']),
        ('FECHA LÍMITE DE PAGO', datos['fecha_limite_pago']),
        ('CARGA CONECTADA kW', carga),
        ('DEMANDA CONTRATADA kW', demanda_cta),
        ('CORTE A PARTIR', datos['corte_partir']),
        ('TARIFA', c['tarifa']),
        ('MULTIPLICADOR', c['multiplicador']),
        ('NO HILOS', c['no_hilos']),
        ('NO. MEDIDOR', c['no_medidor']),
    ]
    fila_serv_1 = ''.join(
        _html_servicio_celda(etq, val) for etq, val in campos_servicio[:5]
    )
    fila_serv_2 = ''.join(
        _html_servicio_celda(etq, val) for etq, val in campos_servicio[5:]
    )

    return f"""
<div class="cfe-recibo-wrap">
<div class="cfe-recibo">
  <div class="cfe-recibo-sim">SIMULACIÓN BESS · {datos['escenario']} · No sustituye el recibo oficial CFE</div>
  <table class="cfe-layout-table cfe-recibo-top">
    <tr>
      <td class="cfe-emisor" width="58%">
        <table class="cfe-layout-table cfe-emisor">
          <tr>
            <td class="cfe-logo-block" align="center" valign="middle"><div class="cfe-logo-inner">{logo_cfe}</div></td>
            <td class="cfe-emisor-texto">
              <div class="cfe-emisor-nombre">Comisión Federal de Electricidad</div>
              <div class="cfe-emisor-dir">Av. Paseo de la Reforma 164, Col. Juárez,<br>
              Alcaldía: Cuauhtémoc, C.P. 06600, Ciudad de México.</div>
              <div class="cfe-emisor-rfc">RFC: CFE370814QI0</div>
            </td>
          </tr>
        </table>
      </td>
      <td class="cfe-receptor" width="42%">
        <div class="cfe-receptor-etq">DATOS DEL RECEPTOR</div>
        <div class="cfe-receptor-nombre">{c['razon_social']}</div>
        <div class="cfe-receptor-dir">{dir_html}</div>
      </td>
    </tr>
  </table>
  <table class="cfe-layout-table cfe-servicio">
    <tr>{fila_serv_1}</tr>
    <tr>{fila_serv_2}</tr>
  </table>
  <div class="cfe-periodo">
    <span class="cfe-periodo-etq">PERIODO FACTURADO:</span>
    <b>{datos['periodo_facturado']}</b>
    <span class="cfe-periodo-dias">· {datos['dias_mes']} días acumulados · corte {datos['fecha_corte'].strftime('%d/%m/%Y')}</span>
  </div>
  <table class="cfe-layout-table cfe-total-wrap">
    <tr>
      <td class="cfe-total-left" width="68%">
        <div class="cfe-total-label">TOTAL A PAGAR:</div>
        <div class="cfe-total-letras">{_monto_a_letras_mxn(d['total'])}</div>
      </td>
      <td class="cfe-total-monto-box" width="32%" align="center">
        <div class="cfe-total-monto">{_fmt_mxn_entero(d['total'])}</div>
      </td>
    </tr>
  </table>
  <table class="cfe-layout-table cfe-body">
    <tr>
      <td class="cfe-consumo-panel">
        <div class="cfe-panel-title">Consumo</div>
        <table class="cfe-mini-table">
          <thead><tr><th>Concepto</th><th>Medida</th></tr></thead>
          <tbody>
            <tr><td>kWh base</td><td class="num">{kwh['base']:,}</td></tr>
            <tr><td>kWh intermedia</td><td class="num">{kwh['intermedio']:,}</td></tr>
            <tr><td>kWh punta</td><td class="num">{kwh['punta']:,}</td></tr>
            <tr><td>kW base</td><td class="num">{kw['base']:,}</td></tr>
            <tr><td>kW intermedia</td><td class="num">{kw['intermedio']:,}</td></tr>
            <tr><td>kW punta</td><td class="num">{kw['punta']:,}</td></tr>
            <tr><td>KWMax</td><td class="num">{kw['kw_max']:,}</td></tr>
            <tr><td>kVArh</td><td class="num">{kvarh_txt}</td></tr>
            <tr><td>Factor de potencia %</td><td class="num">{fp_txt}</td></tr>
          </tbody>
        </table>
      </td>
      <td class="cfe-mem-panel">
        <div class="cfe-panel-title">Costos de la energía en el Mercado Eléctrico Mayorista</div>
        <table class="cfe-mem-table">
          <thead>
            <tr>
              <th>Concepto</th><th>$/kWh</th><th>$/kW</th><th>Importe (MXN)</th>
            </tr>
          </thead>
          <tbody>{filas_mem}</tbody>
        </table>
        <div class="cfe-mem-nota">
          (1) SCnMEM: servicios del Mercado.
        </div>
      </td>
    </tr>
  </table>
  <div class="cfe-desglose">
    <div class="cfe-panel-title">Desglose del importe a pagar</div>
    <table class="cfe-desglose-table">
      <tbody>
        <tr><td>Cargo Fijo</td><td class="num">{_fmt_mxn_decimal(d['cargo_fijo'])}</td></tr>
        <tr><td>Energía</td><td class="num">{_fmt_mxn_decimal(d['energia'])}</td></tr>
        <tr><td>Capacidad ({datos['capacidad_kw']:,} kW · {datos['capacidad_criterio']})</td><td class="num">{_fmt_mxn_decimal(d['capacidad'])}</td></tr>
        <tr><td>Cargo FP</td><td class="num">{_fmt_cargo_fp_recibo(d['cargo_fp'])}</td></tr>
        <tr><td>Subtotal</td><td class="num">{_fmt_mxn_decimal(d['subtotal'])}</td></tr>
        <tr><td>IVA 16%</td><td class="num">{_fmt_mxn_decimal(d['iva'])}</td></tr>
        <tr class="cfe-desglose-total"><td>Facturación del periodo (simulada)</td><td class="num">{_fmt_mxn_decimal(d['total'])}</td></tr>
      </tbody>
    </table>
  </div>
  <div class="cfe-footnote">
    Documento informativo generado por el sistema BESS · IUSASOL. No sustituye el aviso recibo oficial de CFE.
  </div>
</div>
</div>
"""

def _nombre_archivo_recibo(fecha, prefijo, con_bess):
    escenario = 'ConBESS' if con_bess else 'SinBESS'
    return f'Recibo_{prefijo}_{escenario}_{fecha.strftime("%Y%m%d")}.pdf'

_CHROMIUM_LAUNCH_ARGS = (
    '--no-sandbox',
    '--disable-setuid-sandbox',
    '--disable-dev-shm-usage',
    '--disable-gpu',
)

@st.cache_resource(show_spinner='Preparando Chromium para PDF...')
def _ensure_playwright_chromium():
    """Instala el navegador Chromium si falta (necesario en Streamlit Cloud)."""
    from pathlib import Path

    browsers = Path.home() / '.cache' / 'ms-playwright'
    if browsers.exists() and any(browsers.glob('chromium-*')):
        return True

    result = subprocess.run(
        [sys.executable, '-m', 'playwright', 'install', 'chromium'],
        capture_output=True,
        text=True,
    )
    if result.returncode != 0:
        detail = (result.stderr or result.stdout or '').strip()
        raise RuntimeError(
            'No se pudo instalar Chromium para Playwright.'
            + (f' {detail}' if detail else '')
        )
    return True

@st.cache_data(show_spinner='Generando PDF del recibo...')
def _html_a_pdf_playwright(html_doc, doc_key):
    """Convierte HTML del recibo a PDF carta (Playwright/Chromium)."""
    _ensure_playwright_chromium()
    from playwright.sync_api import sync_playwright

    margin = {'top': '8mm', 'bottom': '8mm', 'left': '8mm', 'right': '8mm'}
    altura_util_px = 980

    with sync_playwright() as playwright:
        browser = playwright.chromium.launch(
            headless=True,
            args=list(_CHROMIUM_LAUNCH_ARGS),
        )
        try:
            page = browser.new_page(viewport={'width': 920, 'height': 1400})
            page.set_content(html_doc, wait_until='load')
            altura_recibo = page.evaluate(
                '() => document.querySelector(".cfe-recibo").getBoundingClientRect().height'
            )
            escala = min(1.0, altura_util_px / altura_recibo)
            return page.pdf(
                format='Letter',
                print_background=True,
                margin=margin,
                scale=escala,
            )
        finally:
            browser.close()

def generar_recibo_pdf_bytes(datos):
    """PDF carta vertical: render Chromium del mismo HTML/CSS que la pantalla."""
    html_doc = render_html_recibo_documento(datos)
    doc_key = hashlib.sha256(html_doc.encode('utf-8')).hexdigest()
    return _html_a_pdf_playwright(html_doc, doc_key)


def render_html_recibo_documento(datos):
    """Documento HTML completo para exportar a PDF (mismo aspecto que pantalla)."""
    css = _css_recibo_cfe(for_pdf=True)
    cuerpo = render_html_recibo_cfe(datos)
    escenario = html.escape(datos['escenario'])
    return f"""<!DOCTYPE html>
<html lang="es">
<head>
<meta charset="utf-8">
<title>Recibo simulado CFE · {escenario}</title>
<style>
@page {{ size: letter portrait; margin: 8mm; }}
html, body {{
    margin: 0;
    padding: 0;
    background: #fff;
    -webkit-print-color-adjust: exact;
    print-color-adjust: exact;
}}
body {{ text-align: center; }}
.cfe-recibo-wrap {{ display: inline-block; text-align: left; }}
.cfe-recibo {{ page-break-inside: avoid; break-inside: avoid; }}
{css}
</style>
</head>
<body>
{cuerpo}
</body>
</html>"""

def _render_recibo_escenario(fecha, prefijo, con_bess, tarifas):
    escenario = 'Con BESS' if con_bess else 'Sin BESS'
    mes_label = fecha.strftime('%m/%Y')

    res_energia = calcular_costo_energia_mes(fecha, prefijo, con_bess=con_bess, tarifas=tarifas)
    if res_energia is None:
        st.warning(f"No hay datos de energía acumulada para {mes_label} ({escenario}).")
        return

    res_cfe = calcular_criterio_cfe(fecha, prefijo, con_bess=con_bess, tarifas=tarifas)
    datos = construir_datos_recibo_cfe(
        fecha, prefijo, con_bess, res_energia, res_cfe, tarifas
    )

    with st.container(border=False):
        st.markdown(render_html_recibo_cfe(datos), unsafe_allow_html=True)
        pdf_name = _nombre_archivo_recibo(fecha, prefijo, con_bess)
        try:
            pdf_bytes = generar_recibo_pdf_bytes(datos)
        except Exception as exc:
            st.error(
                'No se pudo generar el PDF del recibo. '
                'La vista en pantalla sigue disponible.'
            )
            st.caption(str(exc))
        else:
            _render_boton_descarga_archivo(
                pdf_bytes,
                pdf_name,
                mime_type='application/pdf',
                etiqueta='Descargar recibo',
            )

def tab_recibo(df, prefijo):
    """Recibo estimado con/sin BESS para el mes al día seleccionado."""
    if df is None or len(df) == 0:
        st.warning('No hay datos disponibles')
        return

    if 'DATETIME' not in df.columns:
        df = df.copy()
        df['DATETIME'] = pd.to_datetime(df['FECHA_HORA'], format='%d/%m/%Y %H:%M')

    fecha_min = df['DATETIME'].min().date()
    fecha_max = df['DATETIME'].max().date()
    fecha_def = datetime.now().date() - timedelta(days=1)
    fecha_def = max(fecha_min, min(fecha_def, fecha_max))

    fecha_sel = render_selector_fecha_unica(
        'Recibo',
        'Fecha de corte para el acumulado mensual del recibo estimado.',
        'Fecha de corte',
        fecha_def,
        fecha_min,
        fecha_max,
        key=f'fecha_recibo_{prefijo}',
    )

    tarifas = cargar_tarifas()
    estado_bess = estado_datos_sin_bess(prefijo)
    tab_sin, tab_con = st.tabs(['Sin BESS', 'Con BESS'])

    with tab_sin:
        if not estado_bess['energia']:
            st.warning(
                'No hay columnas sin BESS en ENERGIA_*_POR_DIA.csv. '
                'Procesa los datos desde el panel de administración.'
            )
        else:
            _render_recibo_escenario(fecha_sel, prefijo, con_bess=False, tarifas=tarifas)

    with tab_con:
        _render_recibo_escenario(fecha_sel, prefijo, con_bess=True, tarifas=tarifas)

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

def _fila_por_fecha(df, fecha):
    if df is None:
        return None
    fecha_str = fecha.strftime('%d/%m/%Y')
    filas = df[df['FECHA'] == fecha_str]
    return filas.iloc[0] if len(filas) > 0 else None

def _cargar_acumulados(prefijo):
    ruta = os.path.join(DIRECTORIO_REPORTES, f'ACUMULADOS_{prefijo}.csv')
    if not os.path.exists(ruta):
        return None
    df = pd.read_csv(ruta)
    df['FECHA_DT'] = pd.to_datetime(df['FECHA'], format='%d/%m/%Y')
    return df

def _formatear_celda_demanda(fila, clave_periodo, tipo_bess):
    col_kw = f'{clave_periodo}_DEM_{tipo_bess}_MAX'
    col_fh = f'{clave_periodo}_DEM_{tipo_bess}_MAX_FECHA_HORA'
    if col_kw not in fila.index:
        return '—', '—'
    kw = pd.to_numeric(fila.get(col_kw, 0), errors='coerce')
    kw = 0 if pd.isna(kw) else kw
    fh = fila.get(col_fh, '') or '—'
    if pd.isna(fh) or fh == '':
        fh = '—'
    return f'{redondear_arriba_kw(kw):,}', fh

def _construir_tabla_demanda_acumulados(fila):
    if fila is None:
        return None
    periodos = [
        ('Base', 'BASE'),
        ('Intermedio', 'INTERMEDIO'),
        ('Punta', 'PUNTA'),
    ]
    filas = []
    for nombre, clave in periodos:
        con_kw, con_fh = _formatear_celda_demanda(fila, clave, 'CON_BESS')
        sin_kw, sin_fh = _formatear_celda_demanda(fila, clave, 'SIN_BESS')
        filas.append({
            'Periodo': nombre,
            'Con BESS (kW)': con_kw,
            'Hora con BESS': con_fh,
            'Sin BESS (kW)': sin_kw,
            'Hora sin BESS': sin_fh,
        })
    return pd.DataFrame(filas)

def construir_tabla_demanda_max_mes(fecha, prefijo):
    """Demanda máxima del mes por periodo (valor y hora pico en ACUMULADOS_*.csv)."""
    df = _cargar_acumulados(prefijo)
    if df is None:
        return None
    mes = pd.Period(fecha, freq='M')
    df_mes = df[df['FECHA_DT'].dt.to_period('M') == mes]
    if df_mes.empty:
        return None
    fila = df_mes.loc[df_mes['FECHA_DT'].idxmax()]
    return _construir_tabla_demanda_acumulados(fila)

def obtener_demanda_rolada_punta(fecha, prefijo, con_bess=True):
    """Demanda rolada máxima en horario punta (kW) al día indicado."""
    fila = _fila_por_fecha(_cargar_acumulados(prefijo), fecha)
    if fila is None:
        return None
    tipo = 'CON_BESS' if con_bess else 'SIN_BESS'
    col = f'PUNTA_DEM_{tipo}_MAX'
    if col not in fila.index:
        return None
    kw = pd.to_numeric(fila.get(col, 0), errors='coerce')
    if pd.isna(kw):
        return 0
    return redondear_arriba_kw(kw)

def acumulados_tiene_demanda_sin_bess(prefijo):
    df = _cargar_acumulados(prefijo)
    if df is None:
        return False
    return 'BASE_DEM_SIN_BESS_MAX' in df.columns

def estilizar_tabla_demanda_periodo(df_tabla):
    styler = df_tabla.style.set_properties(
        subset=['Periodo'],
        **{'font-weight': '600', 'text-align': 'left'}
    )
    for idx, periodo in df_tabla['Periodo'].items():
        bg = PERIODO_BG.get(periodo, '#f8fafc')
        styler = styler.set_properties(
            subset=pd.IndexSlice[idx, ['Con BESS (kW)', 'Hora con BESS']],
            **{'background-color': bg, 'text-align': 'right'}
        )
        styler = styler.set_properties(
            subset=pd.IndexSlice[idx, ['Sin BESS (kW)', 'Hora sin BESS']],
            **{'background-color': bg, 'text-align': 'right', 'opacity': '0.92'}
        )
    styler = styler.set_table_styles([
        {'selector': 'thead th', 'props': [
            ('background-color', '#2c3e50'), ('color', 'white'),
            ('font-weight', '700'), ('text-align', 'center'), ('padding', '8px')
        ]},
    ], overwrite=False)
    return styler

def _sumar_columnas_en_rango(ruta_csv, fecha_inicio, fecha_fin, columnas):
    resultado = {c: 0.0 for c in columnas}
    if not os.path.exists(ruta_csv):
        return resultado
    df = pd.read_csv(ruta_csv)
    df['FECHA_DT'] = pd.to_datetime(df['FECHA'], format='%d/%m/%Y')
    mask = (df['FECHA_DT'].dt.date >= fecha_inicio) & (df['FECHA_DT'].dt.date <= fecha_fin)
    df_r = df[mask]
    for col in columnas:
        if col in df_r.columns:
            resultado[col] = df_r[col].sum()
    return resultado

def _celdas_kwh_tabla(base, intermedio, punta):
    """kWh por periodo redondeados; total = suma de periodos redondeados."""
    b = kwh_para_calculo(base)
    i = kwh_para_calculo(intermedio)
    p = kwh_para_calculo(punta)
    t = b + i + p
    return f"{b:,}", f"{i:,}", f"{p:,}", f"{t:,}"

def calcular_detalle_energia_periodo(fecha_inicio, fecha_fin, prefijo):
    """Calcula filas de la tabla de energía según el rango seleccionado."""
    rango_un_dia = fecha_inicio == fecha_fin
    rango_label = (
        fecha_inicio.strftime('%d/%m/%Y')
        if rango_un_dia
        else f"{fecha_inicio.strftime('%d/%m/%Y')} al {fecha_fin.strftime('%d/%m/%Y')}"
    )

    ruta_acumulados = os.path.join(DIRECTORIO_REPORTES, f'ACUMULADOS_{prefijo}.csv')
    ruta_med_dia = os.path.join(DIRECTORIO_REPORTES, f'ENERGIA_{prefijo}_POR_DIA.csv')
    ruta_bess_dia = os.path.join(DIRECTORIO_REPORTES, 'ENERGIA_BESS_POR_DIA.csv')

    df_acum = pd.read_csv(ruta_acumulados) if os.path.exists(ruta_acumulados) else None
    fila_acum_fin = _fila_por_fecha(df_acum, fecha_fin)

    if rango_un_dia:
        titulo_tabla = f"Detalle de Energía por Periodo · acumulado al {fecha_fin.strftime('%d/%m/%Y')}"
        lbl_consumo = 'Consumo Mensual (kWh)'

        if fila_acum_fin is not None:
            consumo_base = _a_num(fila_acum_fin.get('BASE_REC_ACUM', 0))
            consumo_intermedio = _a_num(fila_acum_fin.get('INTERMEDIO_REC_ACUM', 0))
            consumo_punta = _a_num(fila_acum_fin.get('PUNTA_REC_ACUM', 0))
            demanda_base = redondear_arriba_kw(fila_acum_fin.get('BASE_DEM_CON_BESS_MAX', 0))
            demanda_intermedio = redondear_arriba_kw(fila_acum_fin.get('INTERMEDIO_DEM_CON_BESS_MAX', 0))
            demanda_punta = redondear_arriba_kw(fila_acum_fin.get('PUNTA_DEM_CON_BESS_MAX', 0))
        else:
            consumo_base = consumo_intermedio = consumo_punta = 0
            demanda_base = demanda_intermedio = demanda_punta = 0
    else:
        titulo_tabla = f"Detalle de Energía por Periodo · {rango_label}"
        lbl_consumo = 'Consumo del Periodo (kWh)'

        sums_med = _sumar_columnas_en_rango(
            ruta_med_dia, fecha_inicio, fecha_fin,
            ['BASE_REC', 'INTERMEDIO_REC', 'PUNTA_REC']
        )
        consumo_base = sumar_energia(sums_med['BASE_REC'])
        consumo_intermedio = sumar_energia(sums_med['INTERMEDIO_REC'])
        consumo_punta = sumar_energia(sums_med['PUNTA_REC'])

        if fila_acum_fin is not None:
            demanda_base = redondear_arriba_kw(fila_acum_fin.get('BASE_DEM_CON_BESS_MAX', 0))
            demanda_intermedio = redondear_arriba_kw(fila_acum_fin.get('INTERMEDIO_DEM_CON_BESS_MAX', 0))
            demanda_punta = redondear_arriba_kw(fila_acum_fin.get('PUNTA_DEM_CON_BESS_MAX', 0))
        else:
            demanda_base = demanda_intermedio = demanda_punta = 0

    # Carga, descarga y arbitraje: siempre estrictamente al rango seleccionado
    lbl_carga = 'Carga BESS del Periodo (kWh)'
    lbl_descarga = 'Descarga BESS del Periodo (kWh)'
    resumen_periodo = f"Periodo ({rango_label})"

    sums_bess = _sumar_columnas_en_rango(
        ruta_bess_dia, fecha_inicio, fecha_fin,
        ['BASE_REC', 'INTERMEDIO_REC', 'PUNTA_REC', 'BASE_ENT', 'INTERMEDIO_ENT', 'PUNTA_ENT']
    )
    carga_base = sumar_energia(sums_bess['BASE_REC'])
    carga_intermedio = sumar_energia(sums_bess['INTERMEDIO_REC'])
    carga_punta = sumar_energia(sums_bess['PUNTA_REC'])
    descarga_base = sumar_energia(sums_bess['BASE_ENT'])
    descarga_intermedio = sumar_energia(sums_bess['INTERMEDIO_ENT'])
    descarga_punta = sumar_energia(sums_bess['PUNTA_ENT'])

    tarifas = cargar_tarifas()
    mes_num = fecha_fin.month
    precio_base = tarifas['Base'].get(mes_num, 0)
    precio_intermedio = tarifas['Intermedio'].get(mes_num, 0)
    precio_punta = tarifas['Punta'].get(mes_num, 0)

    if energia_diaria_tiene_sin_bess(prefijo):
        res_con = calcular_costo_energia_rango(
            fecha_inicio, fecha_fin, prefijo, con_bess=True, tarifas=tarifas
        )
        res_sin = calcular_costo_energia_rango(
            fecha_inicio, fecha_fin, prefijo, con_bess=False, tarifas=tarifas
        )
        if res_con is not None and res_sin is not None:
            arb = calcular_arbitraje_desde_costos(res_sin, res_con)
            arbitraje_base = arb['base']
            arbitraje_intermedio = arb['intermedio']
            arbitraje_punta = arb['punta']
            arbitraje_total = arb['total']
        else:
            arbitraje_base, arbitraje_intermedio, arbitraje_punta, arbitraje_total = (
                _calcular_arbitraje_bess_periodo(
                    carga_base, carga_intermedio, carga_punta,
                    descarga_base, descarga_intermedio, descarga_punta,
                    precio_base, precio_intermedio, precio_punta,
                )
            )
    else:
        arbitraje_base, arbitraje_intermedio, arbitraje_punta, arbitraje_total = (
            _calcular_arbitraje_bess_periodo(
                carga_base, carga_intermedio, carga_punta,
                descarga_base, descarga_intermedio, descarga_punta,
                precio_base, precio_intermedio, precio_punta,
            )
        )

    c_b, c_i, c_p, c_t = _celdas_kwh_tabla(consumo_base, consumo_intermedio, consumo_punta)
    g_b, g_i, g_p, g_t = _celdas_kwh_tabla(carga_base, carga_intermedio, carga_punta)
    d_b, d_i, d_p, d_t = _celdas_kwh_tabla(descarga_base, descarga_intermedio, descarga_punta)

    data = [['Periodo', 'Base', 'Intermedio', 'Punta', 'Total']]
    data.append([lbl_consumo, c_b, c_i, c_p, c_t])
    data.append(['Demanda Rolada (kW)', f'{demanda_base:,}', f'{demanda_intermedio:,}', f'{demanda_punta:,}', f'{demanda_punta:,}'])
    data.append([lbl_carga, g_b, g_i, g_p, g_t])
    data.append([lbl_descarga, d_b, d_i, d_p, d_t])
    data.append(['Arbitraje de Energía (MXN)', f'${arbitraje_base:,.2f}', f'${arbitraje_intermedio:,.2f}', f'${arbitraje_punta:,.2f}', f'${arbitraje_total:,.2f}'])

    return {
        'titulo_tabla': titulo_tabla,
        'resumen_periodo': resumen_periodo,
        'df_tabla': pd.DataFrame(data[1:], columns=data[0]),
        'arbitraje_base': arbitraje_base,
        'arbitraje_intermedio': arbitraje_intermedio,
        'arbitraje_punta': arbitraje_punta,
        'arbitraje_total': arbitraje_total,
        'carga_total': kwh_para_calculo(carga_base) + kwh_para_calculo(carga_intermedio) + kwh_para_calculo(carga_punta),
        'descarga_total': kwh_para_calculo(descarga_base) + kwh_para_calculo(descarga_intermedio) + kwh_para_calculo(descarga_punta),
        'rango_label': rango_label,
    }

# ========== ESTILOS CSS ==========
def aplicar_estilos():
    st.markdown("""
    <style>
        [data-testid="stAppViewContainer"]:not(:has(.login-page-marker)) > .main .block-container,
        [data-testid="stAppViewContainer"]:not(:has(.login-page-marker)) [data-testid="stMainBlockContainer"],
        [data-testid="stAppViewContainer"]:not(:has(.login-page-marker)) section[data-testid="stMain"] > div {
            max-width: unset !important;
            width: 100% !important;
        }
        [data-testid="stAppViewContainer"]:not(:has(.login-page-marker)) > .main {
            flex: 1 1 0% !important;
        }
        .main-container { padding: 0 10px; }
        .section-container {
            background: #ffffff;
            border-radius: 12px;
            padding: 20px 24px;
            margin-bottom: 20px;
            box-shadow: 0 2px 8px rgba(0,0,0,0.06);
            border: 1px solid #f0f0f0;
        }
        .section-title {
            font-size: 17px;
            font-weight: 600;
            color: #1a5276;
            margin: 0 0 6px 0;
            padding-bottom: 8px;
            border-bottom: 2px solid #e8ecef;
        }
        .section-title-sm {
            font-size: 14px;
            font-weight: 600;
            color: #1a5276;
            margin: 0 0 8px 0;
            padding-bottom: 6px;
            border-bottom: 1px solid #e8ecef;
        }
        .section-desc {
            font-size: 12px;
            color: #718096;
            margin: 0 0 14px 0;
            line-height: 1.45;
        }
        .tabla-bloque {
            background: #f8fafc;
            border: 1px solid #e2e8f0;
            border-radius: 10px;
            padding: 4px;
            margin: 10px 0 16px 0;
        }
        div[data-testid="stVerticalBlockBorderWrapper"] div[data-testid="stDataFrame"] {
            border: 1px solid #e2e8f0;
            border-radius: 10px;
            overflow: hidden;
            background: #f8fafc;
            margin: 8px 0 14px 0;
        }
        .app-header {
            display: flex;
            align-items: center;
            gap: 18px;
            background: transparent;
            border-radius: 0;
            padding: 0;
            border: none;
            margin-bottom: 0;
        }
        .contexto-medidor {
            font-size: 13px;
            color: #4a5568;
            margin: 0 0 10px 0;
        }
        .panel-controles {
            background: #f8fafc;
            border-radius: 10px;
            padding: 14px 16px;
            border: 1px solid #e8ecef;
            margin-bottom: 16px;
        }
        .app-header-title {
            margin: 0;
            font-size: 1.55rem;
            color: #1a5276;
            font-weight: 700;
        }
        .app-header-sub {
            margin: 4px 0 0;
            color: #718096;
            font-size: 0.88rem;
        }
        .app-header-badge {
            color: #1a5276;
            font-weight: 600;
        }
        
        div[data-testid="stVerticalBlockBorderWrapper"]:has(.stDateInput) {
            background: #f8fafc;
            border-radius: 12px;
            padding: 12px 16px;
            border-color: #e8ecef !important;
            margin-bottom: 28px;
        }
        div[data-testid="stVerticalBlockBorderWrapper"]:has(.panel-fecha-unica-anchor) {
            padding: 8px 12px !important;
            margin-bottom: 12px !important;
            border-radius: 10px !important;
        }
        div[data-testid="stVerticalBlockBorderWrapper"]:has(.panel-fecha-unica-anchor) .section-title-sm {
            margin: 0 0 2px 0;
            padding-bottom: 4px;
            font-size: 13px;
        }
        div[data-testid="stVerticalBlockBorderWrapper"]:has(.panel-fecha-unica-anchor) .section-desc {
            margin: 0 0 6px 0;
            font-size: {fs(11)}px;
            line-height: 1.35;
        }
        div[data-testid="stVerticalBlockBorderWrapper"]:has(.panel-fecha-unica-anchor) .stDateInput label {
            font-size: 12px !important;
        }
        div[data-testid="stVerticalBlockBorderWrapper"]:has(.panel-fecha-unica-anchor) .stDateInput > div {
            min-height: 0 !important;
            padding: 0 8px !important;
        }
        div[data-testid="stVerticalBlockBorderWrapper"]:has(.panel-fecha-unica-anchor) .metric-compact {
            padding: 6px 6px;
        }
        div[data-testid="stVerticalBlockBorderWrapper"]:has(.panel-fecha-unica-anchor) .metric-compact .label {
            font-size: {fs(10)}px;
            margin-bottom: 2px;
        }
        div[data-testid="stVerticalBlockBorderWrapper"]:has(.panel-fecha-unica-anchor) .metric-compact .value {
            font-size: 13px;
        }
        div[data-testid="stVerticalBlockBorderWrapper"]:has(.panel-fecha-unica-anchor) [data-testid="column"] {
            padding-top: 0;
            padding-bottom: 0;
        }
        div[data-testid="stVerticalBlockBorderWrapper"]:not(:has(.stDateInput)):not(:has(form)) {
            background: #ffffff;
            border-radius: 12px;
            padding: 18px 20px;
            border-color: #e2e8f0 !important;
            border-width: 1px !important;
            margin-bottom: 18px;
            box-shadow: 0 1px 6px rgba(26, 82, 118, 0.05);
        }
        div[data-testid="stTabs"] {
            margin-top: 4px;
        }
        div[data-testid="stTabs"] button {
            font-size: 16px !important;
        }
        div[data-testid="stTabs"] button p {
            font-size: 16px !important;
        }
        div[data-testid="stTabs"] div[data-testid="stVerticalBlockBorderWrapper"] {
            box-shadow: none;
            border: none;
            padding: 0;
            margin-bottom: 12px;
            background: transparent;
        }
        div[data-testid="stVerticalBlockBorderWrapper"]:has(.stDateInput) .stDateInput > div {
            background: white;
            border-radius: 8px;
            border: 1px solid #d5d8dc;
            padding: 2px 10px;
        }
        .fecha-resumen {
            background: linear-gradient(135deg, #e8f4f8 0%, #d4e9f7 100%);
            border-radius: 8px;
            padding: 10px 16px;
            border-left: 4px solid #1a5276;
            font-size: 13px;
            margin: 8px 0 12px 0;
        }
        
        .metric-card {
            background: white;
            border-radius: 10px;
            padding: 16px;
            text-align: center;
            border: 1px solid #e8ecef;
            box-shadow: 0 1px 4px rgba(0,0,0,0.04);
        }
        .metric-card .icon { display: none; }
        .metric-card .label { font-size: 13px; color: #718096; font-weight: 500; }
        .metric-card .value { font-size: 24px; font-weight: 700; color: #1a202c; }
        .metric-card .sub { font-size: 12px; color: #a0aec0; }

        .metric-compact {
            background: #fafbfc;
            border-radius: 8px;
            padding: 10px 8px;
            text-align: center;
            border: 1px solid #e8ecef;
        }
        .metric-compact .label {
            font-size: {fs(11)}px;
            color: #718096;
            font-weight: 500;
            line-height: 1.3;
            margin-bottom: 4px;
        }
        .metric-compact .value {
            font-size: 15px;
            font-weight: 600;
            color: #1a202c;
            line-height: 1.25;
        }

        .sidebar-tarifas-grid {
            display: flex;
            flex-direction: column;
            gap: 6px;
            margin-top: 4px;
        }
        .sidebar-tarifa-item {
            background: #f8fafc;
            border-radius: 6px;
            padding: 6px 10px;
            border: 1px solid #e8ecef;
            display: flex;
            justify-content: space-between;
            align-items: center;
            gap: 8px;
        }
        .sidebar-tarifa-item .label {
            font-size: 12px;
            color: #718096;
            font-weight: 500;
            line-height: 1.2;
            flex-shrink: 0;
        }
        .sidebar-tarifa-item .value {
            font-size: 13px;
            font-weight: 600;
            color: #1a202c;
            line-height: 1.25;
            text-align: right;
        }
        
        .arbitraje-card {
            border-radius: 10px;
            padding: 14px;
            text-align: center;
            border-left: 4px solid #27ae60;
            background: #f0fff4;
        }
        .arbitraje-card.negativo {
            border-left-color: #e74c3c;
            background: #fff5f5;
        }
        .arbitraje-card .periodo { font-size: 13px; font-weight: 600; color: #4a5568; }
        .arbitraje-card .valor { font-size: 20px; font-weight: 700; }
        .arbitraje-card .valor.positivo { color: #27ae60; }
        .arbitraje-card .valor.negativo { color: #e74c3c; }

        .capacidad-comparacion {
            display: flex;
            align-items: stretch;
            gap: 12px;
            margin: 8px 0 12px 0;
        }
        @media (max-width: 960px) {
            .capacidad-comparacion {
                flex-direction: column;
            }
            .cap-centro {
                order: -1;
            }
        }
        .cap-bloque {
            flex: 1;
            border-radius: 10px;
            padding: 16px 14px;
            text-align: center;
            border: 1px solid #e8ecef;
        }
        .cap-bloque.cap-sin {
            background: #fff5f5;
            border-left: 4px solid #e74c3c;
        }
        .cap-bloque.cap-con {
            background: #f0fff4;
            border-left: 4px solid #27ae60;
        }
        .cap-etiqueta {
            font-size: 12px;
            font-weight: 700;
            text-transform: uppercase;
            letter-spacing: 0.04em;
            color: #718096;
            margin-bottom: 6px;
        }
        .cap-demanda {
            font-size: 13px;
            color: #4a5568;
            margin-bottom: 4px;
        }
        .cap-costo {
            font-size: 22px;
            font-weight: 700;
            color: #1a202c;
        }
        .cap-centro {
            flex: 1.1;
            display: flex;
            flex-direction: column;
            justify-content: center;
            align-items: center;
            border-radius: 12px;
            padding: 14px 10px;
            background: linear-gradient(135deg, #e8f8ef 0%, #d4efdf 100%);
            border: 2px solid #27ae60;
            text-align: center;
        }
        .cap-centro.negativo {
            background: linear-gradient(135deg, #fdecea 0%, #fadbd8 100%);
            border-color: #e74c3c;
        }
        .cap-ahorro-valor {
            font-size: 28px;
            font-weight: 800;
            color: #1e8449;
            line-height: 1.1;
        }
        .cap-centro.negativo .cap-ahorro-valor { color: #c0392b; }
        .cap-ahorro-label {
            font-size: 13px;
            font-weight: 600;
            color: #2c3e50;
            margin-top: 4px;
        }
        .cap-ahorro-sub {
            font-size: 12px;
            color: #718096;
            margin-top: 6px;
        }
        .cap-tarifa {
            font-size: 12px;
            color: #718096;
            text-align: center;
            margin-bottom: 8px;
        }

    """ + _css_recibo_cfe() + """
        
        .stButton button {
            border-radius: 8px;
            font-weight: 500;
        }
        .btn-primary button {
            background: #1a5276;
            color: white;
        }
        .btn-primary button:hover {
            background: #154360;
        }
    </style>
    """, unsafe_allow_html=True)

def aplicar_estilos_login():
    st.markdown("""
    <style>
        [data-testid="stAppViewContainer"]:has(.login-page-marker) [data-testid="stSidebar"] {
            display: none;
        }
        [data-testid="stAppViewContainer"]:has(.login-page-marker) > .main .block-container,
        [data-testid="stAppViewContainer"]:has(.login-page-marker) [data-testid="stMainBlockContainer"],
        [data-testid="stAppViewContainer"]:has(.login-page-marker) section[data-testid="stMain"] > div {
            padding-top: 2.5rem;
            max-width: 100% !important;
            width: 100% !important;
            margin-left: auto !important;
            margin-right: auto !important;
            padding-left: 1rem;
            padding-right: 1rem;
            box-sizing: border-box;
        }
        [data-testid="stAppViewContainer"]:has(.login-page-marker) [data-testid="column"] {
            min-width: 0 !important;
        }
        .login-page-marker {
            display: none;
        }
        .login-brand {
            text-align: center;
            margin-bottom: 1.25rem;
        }
        .login-logo-wrap {
            display: flex;
            justify-content: center;
            margin-bottom: 14px;
        }
        .login-logo-wrap img {
            display: block;
            max-width: min(288px, 100%);
            height: auto;
        }
        .login-title {
            margin: 0 0 6px 0;
            font-size: clamp(1.05rem, 2.2vw, 1.55rem);
            color: #1a5276;
            font-weight: 700;
            white-space: nowrap;
            line-height: 1.2;
        }
        .login-subtitle {
            margin: 0;
            color: #718096;
            font-size: 0.88rem;
            line-height: 1.45;
        }
        [data-testid="stAppViewContainer"]:has(.login-page-marker) div[data-testid="stVerticalBlockBorderWrapper"]:has(form[data-testid="stForm"]) {
            background: white;
            border-radius: 12px;
            box-shadow: 0 1px 6px rgba(26, 82, 118, 0.05);
            border: 1px solid #e2e8f0 !important;
            border-top: 3px solid #1a5276 !important;
            padding: 20px 18px;
            width: 100%;
            box-sizing: border-box;
        }
        [data-testid="stAppViewContainer"]:has(.login-page-marker) div[data-testid="stVerticalBlockBorderWrapper"]:has(form[data-testid="stForm"]) .stTextInput > div > div {
            background: #f8fafc;
            border-radius: 8px;
        }
        [data-testid="stAppViewContainer"]:has(.login-page-marker) div[data-testid="stVerticalBlockBorderWrapper"]:has(form[data-testid="stForm"]) label p {
            white-space: normal;
            word-break: normal;
        }
        [data-testid="stAppViewContainer"]:has(.login-page-marker) div[data-testid="stVerticalBlockBorderWrapper"]:has(form[data-testid="stForm"]) button[kind="primaryFormSubmit"] {
            background: #1a5276;
            border: none;
            border-radius: 8px;
            font-weight: 600;
            white-space: nowrap;
            width: 100%;
        }
        [data-testid="stAppViewContainer"]:has(.login-page-marker) div[data-testid="stVerticalBlockBorderWrapper"]:has(form[data-testid="stForm"]) button[kind="primaryFormSubmit"]:hover {
            background: #154360;
        }
    </style>
    """, unsafe_allow_html=True)

# ========== GRÁFICAS ==========
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

# ========== FUNCIONES DE AUTENTICACIÓN ==========
USUARIOS = {
    'admin': {'password': hashlib.sha256('admin123'.encode()).hexdigest(), 'rol': 'admin', 'nombre': 'Administrador'},
    'user': {'password': hashlib.sha256('user123'.encode()).hexdigest(), 'rol': 'user', 'nombre': 'Usuario'}
}

def init_session():
    if 'autenticado' not in st.session_state:
        st.session_state.autenticado = False
        st.session_state.usuario = None
        st.session_state.rol = None

def login():
    aplicar_estilos_login()
    st.markdown('<div class="login-page-marker"></div>', unsafe_allow_html=True)

    _, col, _ = st.columns([3, 4, 3])
    with col:
        logo_html = obtener_logo_html(288)
        logo_block = (
            f'<div class="login-logo-wrap">'
            f'<div style="background:white;border-radius:10px;padding:8px 14px;'
            f'box-shadow:0 1px 4px rgba(0,0,0,0.04);">{logo_html}</div></div>'
            if logo_html else ''
        )
        st.markdown(f"""
        <div class="login-brand">
            {logo_block}
            <h1 class="login-title">BESS · Sistema de Energía</h1>
            <p class="login-subtitle">Sistema de Procesamiento y Reportes de Energía</p>
        </div>
        """, unsafe_allow_html=True)

        with st.container(border=True):
            with st.form("login"):
                usuario = st.text_input("Usuario", placeholder="Ingresa tu usuario")
                password = st.text_input("Contraseña", type="password", placeholder="Ingresa tu contraseña")
                submit = st.form_submit_button("Iniciar Sesión", use_container_width=True, type="primary")

                if submit and usuario and password:
                    if usuario in USUARIOS and hashlib.sha256(password.encode()).hexdigest() == USUARIOS[usuario]['password']:
                        st.session_state.autenticado = True
                        st.session_state.usuario = usuario
                        st.session_state.rol = USUARIOS[usuario]['rol']
                        st.cache_data.clear()
                        st.rerun()
                    else:
                        st.error("❌ Usuario o contraseña incorrectos")

def logout():
    st.cache_data.clear()
    st.session_state.autenticado = False
    st.session_state.usuario = None
    st.session_state.rol = None
    st.rerun()

# ========== FUNCIONES DE PROCESAMIENTO ==========
def _tarifas_vacias():
    return {t: {i: 0 for i in range(1, 13)} for t in TIPOS_TARIFA}

def ruta_archivo_tarifas():
    return os.path.join(DIRECTORIO_TARIFAS, ARCHIVO_TARIFAS)

def _df_tarifas_plantilla():
    filas = []
    for tipo in TIPOS_TARIFA:
        fila = {'Tarifa': tipo}
        for mes in range(1, 13):
            fila[str(mes)] = 0.0
        filas.append(fila)
    return pd.DataFrame(filas)

def leer_df_tarifas():
    """Lee Tarifas_2026.csv como DataFrame editable (4 filas × 12 meses)."""
    ruta = ruta_archivo_tarifas()
    if not os.path.exists(ruta):
        return _df_tarifas_plantilla()
    try:
        df = pd.read_csv(ruta, encoding='utf-8-sig')
        df.columns = [str(c).strip() for c in df.columns]
        if 'Tarifa' not in df.columns:
            return _df_tarifas_plantilla()
        df['Tarifa'] = df['Tarifa'].astype(str).str.strip()
        tipos_map = {t.lower(): t for t in TIPOS_TARIFA}
        tipos_map.update({
            'distribución': 'Distribucion',
            'transmisión': 'Transmision',
            'cargo fijo': 'CargoFijo',
            'servicios auxiliares': 'ServiciosAuxiliares',
        })
        df['Tarifa'] = df['Tarifa'].str.lower().map(tipos_map).fillna(df['Tarifa'])
        for mes in range(1, 13):
            col = str(mes)
            if col not in df.columns:
                df[col] = 0.0
            df[col] = pd.to_numeric(df[col], errors='coerce').fillna(0.0)
        df = df[df['Tarifa'].isin(TIPOS_TARIFA)].copy()
        presentes = set(df['Tarifa'])
        for tipo in TIPOS_TARIFA:
            if tipo not in presentes:
                fila = {'Tarifa': tipo}
                for mes in range(1, 13):
                    fila[str(mes)] = 0.0
                df = pd.concat([df, pd.DataFrame([fila])], ignore_index=True)
        df = df.set_index('Tarifa').reindex(TIPOS_TARIFA).reset_index()
        return df[['Tarifa'] + [str(m) for m in range(1, 13)]]
    except Exception:
        return _df_tarifas_plantilla()

def validar_df_tarifas(df):
    columnas_mes = [str(m) for m in range(1, 13)]
    if df is None or df.empty:
        return 'No hay datos de tarifas.'
    if 'Tarifa' not in df.columns:
        return 'Falta la columna Tarifa.'
    faltantes = [c for c in columnas_mes if c not in df.columns]
    if faltantes:
        return f'Faltan columnas de mes: {", ".join(faltantes)}.'
    tipos = [str(t).strip() for t in df['Tarifa'].tolist()]
    if tipos != TIPOS_TARIFA:
        return f'Se requieren exactamente las filas: {", ".join(TIPOS_TARIFA)}.'
    for col in columnas_mes:
        valores = pd.to_numeric(df[col], errors='coerce')
        if valores.isna().any():
            return f'Valores no numéricos en el mes {col}.'
        if (valores < 0).any():
            return f'Las tarifas del mes {col} no pueden ser negativas.'
    return None

def guardar_df_tarifas(df):
    error = validar_df_tarifas(df)
    if error:
        return False, error
    ruta = ruta_archivo_tarifas()
    df_guardar = df.copy()
    df_guardar['Tarifa'] = df_guardar['Tarifa'].astype(str).str.strip()
    columnas = ['Tarifa'] + [str(m) for m in range(1, 13)]
    for mes in range(1, 13):
        col = str(mes)
        df_guardar[col] = pd.to_numeric(df_guardar[col], errors='coerce').fillna(0.0).round(4)
    df_guardar = df_guardar[columnas]
    if os.path.exists(ruta):
        marca = datetime.now().strftime('%Y%m%d_%H%M%S')
        backup = ruta.replace('.csv', f'_backup_{marca}.csv')
        shutil.copy2(ruta, backup)
    df_guardar.to_csv(ruta, index=False, encoding='utf-8-sig')
    return True, ARCHIVO_TARIFAS

def cargar_tarifas():
    try:
        df = leer_df_tarifas()
        tarifas = _tarifas_vacias()
        for _, row in df.iterrows():
            tipo = str(row['Tarifa']).strip()
            for mes in range(1, 13):
                tarifas.setdefault(tipo, {i: 0 for i in range(1, 13)})
                tarifas[tipo][mes] = float(row.get(str(mes), 0) or 0)
        return tarifas
    except Exception:
        return _tarifas_vacias()

def _column_config_tarifas():
    config = {
        'Tarifa': st.column_config.TextColumn('Tarifa', disabled=True, width='small'),
    }
    for mes in range(1, 13):
        config[str(mes)] = st.column_config.NumberColumn(
            f'M{mes}',
            min_value=0.0,
            format='%.4f',
            width='small',
        )
    return config

def render_editor_tarifas_sidebar():
    st.caption(f'Archivo: `{ARCHIVO_TARIFAS}` · valores en MXN')
    df_base = leer_df_tarifas()
    df_editado = st.data_editor(
        df_base,
        column_config=_column_config_tarifas(),
        hide_index=True,
        num_rows='fixed',
        use_container_width=True,
        key='editor_tarifas_csv',
    )
    col_guardar, col_recargar = st.columns(2)
    with col_guardar:
        if st.button('Guardar tarifas', use_container_width=True, type='primary', key='btn_guardar_tarifas'):
            ok, msg = guardar_df_tarifas(df_editado)
            if ok:
                st.success(f'Tarifas guardadas en {msg}')
                st.session_state.pop('editor_tarifas_csv', None)
                st.rerun()
            else:
                st.error(msg)
    with col_recargar:
        if st.button('Descartar cambios', use_container_width=True, key='btn_recargar_tarifas'):
            st.session_state.pop('editor_tarifas_csv', None)
            st.rerun()

FACTOR_CFE_CAPACIDAD = 0.74

def dias_transcurridos_mes(fecha):
    """Días transcurridos del mes a la fecha seleccionada."""
    return fecha.day

def _filtrar_mes_hasta_fecha(df, fecha, col_fecha='FECHA_DT'):
    mes = fecha.month
    año = fecha.year
    return df[
        (df[col_fecha].dt.year == año)
        & (df[col_fecha].dt.month == mes)
        & (df[col_fecha].dt.date <= fecha)
    ]

def _obtener_energia_mes_desde_diario(fecha, prefijo, columnas_periodo):
    """Suma energía por periodo desde ENERGIA_*_POR_DIA.csv (mes al día indicado)."""
    ruta = os.path.join(DIRECTORIO_REPORTES, f'ENERGIA_{prefijo}_POR_DIA.csv')
    if not os.path.exists(ruta):
        return None
    df = pd.read_csv(ruta)
    df['FECHA_DT'] = pd.to_datetime(df['FECHA'], format='%d/%m/%Y')
    df_r = _filtrar_mes_hasta_fecha(df, fecha)
    if df_r.empty:
        return None
    por_periodo = {}
    for clave, col in columnas_periodo.items():
        if col not in df_r.columns:
            return None
        por_periodo[clave] = sumar_energia(pd.to_numeric(df_r[col], errors='coerce').fillna(0))
    return {'total': sum(por_periodo.values()), 'por_periodo': por_periodo}

def obtener_energia_con_bess_mes(fecha, prefijo):
    """Energía con BESS por periodos (medidor), del mes al día indicado."""
    return _obtener_energia_mes_desde_diario(fecha, prefijo, {
        'base': 'BASE_REC',
        'intermedio': 'INTERMEDIO_REC',
        'punta': 'PUNTA_REC',
    })

def obtener_energia_sin_bess_mes(fecha, prefijo):
    """Energía sin BESS por periodos, del mes al día indicado (ENERGIA_*_POR_DIA.csv)."""
    return _obtener_energia_mes_desde_diario(fecha, prefijo, {
        'base': 'BASE_REC_SIN_BESS',
        'intermedio': 'INTERMEDIO_REC_SIN_BESS',
        'punta': 'PUNTA_REC_SIN_BESS',
    })

def energia_diaria_tiene_sin_bess(prefijo):
    ruta = os.path.join(DIRECTORIO_REPORTES, f'ENERGIA_{prefijo}_POR_DIA.csv')
    if not os.path.exists(ruta):
        return False
    return 'BASE_REC_SIN_BESS' in pd.read_csv(ruta, nrows=0).columns

def calcular_criterio2_cfe_kw(energia_kwh, dias):
    """Factor de carga CFE: energía total / (0.74 × 24 × días transcurridos)."""
    divisor = FACTOR_CFE_CAPACIDAD * 24 * dias
    return energia_kwh / divisor if divisor > 0 else 0

def calcular_criterio_cfe(fecha, prefijo, con_bess=True, tarifas=None):
    """
    Criterio CFE: capacidad (kW) = min(demanda máx. punta, factor de carga).
    Costo = capacidad × tarifa capacidad del mes.
    """
    demanda_punta = obtener_demanda_rolada_punta(fecha, prefijo, con_bess=con_bess)
    if con_bess:
        energia_info = obtener_energia_con_bess_mes(fecha, prefijo)
    else:
        energia_info = obtener_energia_sin_bess_mes(fecha, prefijo)
    if demanda_punta is None or energia_info is None:
        return None

    dias = dias_transcurridos_mes(fecha)
    energia_kwh = energia_info['total']
    criterio1_kw = redondear_arriba_kw(demanda_punta)
    criterio2_kw = redondear_arriba_kw(calcular_criterio2_cfe_kw(energia_kwh, dias))
    capacidad_kw = min(criterio1_kw, criterio2_kw)
    criterio_aplicado = 'punta' if criterio1_kw <= criterio2_kw else 'factor_carga'

    if tarifas is None:
        tarifas = cargar_tarifas()
    mes = fecha.month
    precio_cap = tarifas.get('Capacidad', {}).get(mes, 0)

    return {
        'criterio1_punta_kw': criterio1_kw,
        'criterio2_factor_kw': criterio2_kw,
        'capacidad_kw': capacidad_kw,
        'criterio_aplicado': criterio_aplicado,
        'energia_kwh': energia_kwh,
        'energia_por_periodo': energia_info['por_periodo'],
        'dias_mes': dias,
        'precio_cap': precio_cap,
        'costo_mxn': redondear_arriba_mxn(capacidad_kw * precio_cap),
    }

def construir_tabla_criterio_cfe(resultado_con, resultado_sin=None):
    filas = []
    for escenario, res in [('Con BESS', resultado_con), ('Sin BESS', resultado_sin)]:
        if res is None:
            continue
        lbl_criterio = (
            'Demanda punta'
            if res['criterio_aplicado'] == 'punta'
            else 'DemandaCalculadaCFE'
        )
        pp = res.get('energia_por_periodo', {})
        filas.append({
            'Escenario': escenario,
            'Energía (kWh)': fmt_kwh(res['energia_kwh']),
            'Base (kWh)': fmt_kwh(pp.get('base', 0)),
            'Intermedio (kWh)': fmt_kwh(pp.get('intermedio', 0)),
            'Punta (kWh)': fmt_kwh(pp.get('punta', 0)),
            'Días transcurridos': res['dias_mes'],
            'Demanda punta (kW)': f"{int(res['criterio1_punta_kw']):,}",
            'DemandaCalculadaCFE': f"{res['criterio2_factor_kw']:,}",
            'Capacidad CFE (kW)': f"{res['capacidad_kw']:,}",
            'Criterio aplicado': lbl_criterio,
            'Costo capacidad (MXN)': f"${res['costo_mxn']:,.2f}",
        })
    return pd.DataFrame(filas) if filas else None

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

# ========== FUNCIONES DE SIDEBAR ==========
def sidebar_branding(es_admin):
    logo_html = obtener_logo_html(288)
    subtitulo = 'Panel de Control' if es_admin else 'Visualizador'
    logo_block = (
        f'<div style="background:white;border-radius:8px;padding:6px 10px;display:inline-block;margin-bottom:8px;">{logo_html}</div>'
        if logo_html else '<h2 style="color:white;margin:0;font-size:20px;">⚡ BESS</h2>'
    )
    st.markdown(f"""
    <div style="background:linear-gradient(135deg,#1a5276,#2e86c1);padding:16px;border-radius:12px;text-align:center;margin-bottom:16px;">
        {logo_block}
        <p style="color:rgba(255,255,255,0.9);margin:4px 0 0;font-size:12px;font-weight:500;">{subtitulo}</p>
    </div>
    """, unsafe_allow_html=True)

def sidebar_admin():
    with st.sidebar:
        sidebar_branding(es_admin=True)
        
        with st.expander("Cargar archivos", expanded=False):
            archivos = st.file_uploader(
                "Archivos CSV (ION, BESS, Banco1)",
                type=['csv'],
                accept_multiple_files=True,
                key="upload"
            )
            if archivos:
                for archivo in archivos:
                    if st.button(f"📤 {archivo.name}", key=f"subir_{archivo.name}"):
                        try:
                            ruta = os.path.join(DIRECTORIO_FUENTE, archivo.name)
                            with open(ruta, 'wb') as f:
                                f.write(archivo.getbuffer())
                            st.success(f"✅ {archivo.name} subido")
                            st.session_state['archivos_subidos'] = True
                        except Exception as e:
                            st.error(f"❌ Error: {e}")
            
            st.divider()
            if st.button("Ver archivos fuente", use_container_width=True):
                archivos_fuente = os.listdir(DIRECTORIO_FUENTE) if os.path.exists(DIRECTORIO_FUENTE) else []
                if archivos_fuente:
                    for a in archivos_fuente:
                        st.write(f"📄 {a}")
                else:
                    st.info("No hay archivos fuente")

        with st.expander("Sincronizar perfiles", expanded=False):
            if st.button("Sincronizar ahora", use_container_width=True, key="sync_perfiles"):
                with st.spinner("Sincronizando..."):
                    try:
                        from bess.data.sync_resumen import html_resumen_sidebar

                        root = os.path.dirname(os.path.abspath(__file__))
                        script = os.path.join(root, "scripts", "sincronizar_perfiles.py")
                        proc = subprocess.run(
                            [sys.executable, script, "--quiet"],
                            cwd=root,
                            capture_output=True,
                            text=True,
                            encoding='utf-8',
                            errors='replace',
                            timeout=600,
                        )
                        salida = (proc.stdout or "").strip()
                        ion_off = "Medidor ION no disponible." in salida or "ION: no disponible" in salida
                        if proc.returncode == 0:
                            if ion_off:
                                st.warning("Medidor ION no disponible. BESS/BANCO y export OK.")
                            else:
                                st.success("Sync completada. Siguiente: **Procesar todo**.")
                            st.session_state["verificado"] = False
                            lineas = [ln.strip() for ln in salida.splitlines() if ln.strip()]
                            if lineas:
                                st.markdown(html_resumen_sidebar(lineas), unsafe_allow_html=True)
                        else:
                            st.error("La sincronizacion fallo.")
                            if salida:
                                st.markdown(
                                    html_resumen_sidebar(salida.splitlines()[:6]),
                                    unsafe_allow_html=True,
                                )
                            err = (proc.stderr or "").strip()
                            if err:
                                st.caption(err[:500])
                    except subprocess.TimeoutExpired:
                        st.error("Tiempo agotado (>10 min). Ejecute el script en consola.")
                    except Exception as e:
                        st.error(f"Error: {e}")

        with st.expander("Procesar datos", expanded=False):
            col1, col2 = st.columns(2)
            
            with col1:
                if st.button("Verificar", use_container_width=True):
                    with st.spinner("Verificando archivos..."):
                        try:
                            from bess_core import verificar_datos_fuente
                            exito, mensaje = verificar_datos_fuente()
                            if exito:
                                st.success(f"✅ {mensaje}")
                                st.session_state['verificado'] = True
                            else:
                                st.error(f"❌ {mensaje}")
                        except Exception as e:
                            st.error(f"❌ Error: {e}")
            
            with col2:
                if st.button("Filtrar", use_container_width=True):
                    with st.spinner("Filtrando datos..."):
                        try:
                            from bess_core import filtrar_datos
                            exito, mensaje = filtrar_datos()
                            if exito:
                                st.success(f"✅ {mensaje}")
                                st.session_state['filtrado'] = True
                            else:
                                st.error(f"❌ {mensaje}")
                        except Exception as e:
                            st.error(f"❌ Error: {e}")
            
            if st.button("Generar reportes", use_container_width=True, type="primary"):
                with st.spinner("Generando reportes..."):
                    try:
                        from bess_core import ejecutar_reporte_bess
                        from bess.config.subestaciones import SUBESTACIONES
                        exito, mensajes = ejecutar_reporte_bess()
                        if "_error" in mensajes:
                            st.error(f"❌ {mensajes['_error']}")
                            if mensajes.get("_traceback"):
                                with st.expander("Detalle del error"):
                                    st.code(mensajes["_traceback"])
                        elif exito:
                            st.success("✅ Reportes generados exitosamente")
                            for sub in SUBESTACIONES:
                                for med in sub.medidores_consumo:
                                    msg = mensajes.get(med.prefijo, "")
                                    if msg:
                                        st.success(f"   {sub.nombre} · {med.etiqueta}: {msg}")
                            st.session_state['reportes_generados'] = True
                        else:
                            st.warning("⚠️ Procesamiento parcial")
                            for sub in SUBESTACIONES:
                                for med in sub.medidores_consumo:
                                    msg = mensajes.get(med.prefijo, "")
                                    if msg:
                                        st.warning(f"   {sub.nombre} · {med.etiqueta}: {msg}")
                    except Exception as e:
                        st.error(f"❌ Error: {e}")
        
            if st.button("Procesar todo", use_container_width=True):
                with st.spinner("Verificando, filtrando y generando reportes..."):
                    try:
                        from bess_core import verificar_datos_fuente, filtrar_datos, ejecutar_reporte_bess
                        from bess.config.subestaciones import SUBESTACIONES
                        exito_v, msg_v = verificar_datos_fuente()
                        if not exito_v:
                            st.error(msg_v)
                        else:
                            exito_f, msg_f = filtrar_datos()
                            if not exito_f:
                                st.error(msg_f)
                            else:
                                exito_r, mensajes = ejecutar_reporte_bess()
                                if "_error" in mensajes:
                                    st.error(f"❌ {mensajes['_error']}")
                                elif exito_r:
                                    st.success("Proceso completo")
                                    for sub in SUBESTACIONES:
                                        for med in sub.medidores_consumo:
                                            msg = mensajes.get(med.prefijo, "")
                                            if msg:
                                                st.success(f"   {sub.nombre} · {med.etiqueta}: {msg}")
                                else:
                                    partes = [
                                        f"{med.etiqueta}: {mensajes.get(med.prefijo, '')}"
                                        for sub in SUBESTACIONES
                                        for med in sub.medidores_consumo
                                        if mensajes.get(med.prefijo)
                                    ]
                                    st.warning("Parcial — " + " · ".join(partes))
                    except Exception as e:
                        st.error(f"Error: {e}")

        with st.expander("Tarifas", expanded=False):
            tarifas = cargar_tarifas()
            mes = datetime.now().month
            nombres_mes = (
                'Enero', 'Febrero', 'Marzo', 'Abril', 'Mayo', 'Junio',
                'Julio', 'Agosto', 'Septiembre', 'Octubre', 'Noviembre', 'Diciembre',
            )
            st.markdown(f"**Mes actual:** {nombres_mes[mes - 1]} {datetime.now().year}")
            st.markdown(html_tarifas_sidebar(tarifas, mes), unsafe_allow_html=True)
            st.divider()
            render_editor_tarifas_sidebar()
        
        st.divider()
        st.caption("Sistema BESS v5.5.0")

def _inyectar_script_sidebar(expandida):
    """Ajusta la sidebar tras el login (Streamlit fija el estado inicial solo al cargar la app)."""
    objetivo = 'true' if expandida else 'false'
    js = f"""
    (function () {{
        function doc() {{
            return window.parent && window.parent.document ? window.parent.document : document;
        }}
        function ajustar() {{
            const d = doc();
            const sidebar = d.querySelector('section[data-testid="stSidebar"]');
            if (!sidebar) return;
            const abierta = sidebar.getAttribute('aria-expanded') === 'true';
            const debeEstarAbierta = {objetivo};
            if (abierta === debeEstarAbierta) return;
            const btn = d.querySelector('[data-testid="stHeader"] button');
            if (btn) btn.click();
        }}
        [80, 250, 600, 1200, 2000].forEach(function (ms) {{
            setTimeout(ajustar, ms);
        }});
    }})();
    """
    markup = f"<script>{js}</script>"
    if hasattr(st, "html"):
        try:
            st.html(markup, height=0)
        except TypeError:
            st.html(markup)
    else:
        components.html(markup, height=0)

def _ajustar_sidebar_por_rol(es_admin):
    _inyectar_script_sidebar(expandida=es_admin)

def sidebar_user():
    with st.sidebar:
        sidebar_branding(es_admin=False)
        st.info("Modo visualización")
        st.caption("Sistema BESS v5.5.0")

# ========== FUNCIONES DE TABS ==========
def tab_dashboard(df, prefijo, medidor):
    with st.container(border=True):
        fecha_inicio, fecha_fin, df_filtrado = render_selector_rango(
            df, prefijo, key_suffix='dashboard', medidor=medidor
        )

    if len(df_filtrado) == 0:
        st.warning("No hay datos en el rango seleccionado")
        return

    rango_label = f"{fecha_inicio.strftime('%d/%m/%Y')} al {fecha_fin.strftime('%d/%m/%Y')}"
    detalle = calcular_detalle_energia_periodo(fecha_inicio, fecha_fin, prefijo)

    carga = sumar_energia(df_filtrado['KWH_REC_BESS'])
    descarga = sumar_energia(df_filtrado['KWH_ENT_BESS'])
    eficiencia = (descarga / carga * 100) if carga > 0 else 0

    with st.container(border=True):
        section_header(f"Resumen del periodo · {rango_label}")
        col1, col2, col3, col4 = st.columns(4)
        with col1:
            st.markdown(f"""
            <div class="metric-card" style="border-top:3px solid {COLORES['carga']};">
                <div class="label">Carga BESS</div>
                <div class="value">{fmt_kwh(carga)}</div>
                <div class="sub">kWh</div>
            </div>
            """, unsafe_allow_html=True)
        with col2:
            st.markdown(f"""
            <div class="metric-card" style="border-top:3px solid {COLORES['descarga']};">
                <div class="label">Descarga BESS</div>
                <div class="value">{fmt_kwh(descarga)}</div>
                <div class="sub">kWh</div>
            </div>
            """, unsafe_allow_html=True)
        with col3:
            st.markdown(f"""
            <div class="metric-card" style="border-top:3px solid {COLORES['primary']};">
                <div class="label">Eficiencia</div>
                <div class="value">{eficiencia:.1f}%</div>
                <div class="sub">{'Óptima' if eficiencia >= 80 else 'Revisar'}</div>
            </div>
            """, unsafe_allow_html=True)
        with col4:
            st.markdown(f"""
            <div class="metric-card" style="border-top:3px solid {COLORES['success']};">
                <div class="label">Arbitraje</div>
                <div class="value">${detalle['arbitraje_total']:,.2f}</div>
                <div class="sub">MXN</div>
            </div>
            """, unsafe_allow_html=True)

    with st.container(border=True):
        section_header("Perfil de carga")
        fig_perfil = graficar_perfil(df_filtrado, prefijo, "")
        st.plotly_chart(fig_perfil, use_container_width=True, config={'displayModeBar': False})

    with st.container(border=True):
        section_header(detalle["titulo_tabla"])
        st.dataframe(
            estilizar_tabla_energia(detalle['df_tabla']),
            use_container_width=True,
            hide_index=True,
        )

    section_header(f"Arbitraje por periodo · {detalle['rango_label']}")
    col1, col2, col3, col4 = st.columns(4)
    for i, periodo in enumerate(['Base', 'Intermedio', 'Punta']):
        valor = [detalle['arbitraje_base'], detalle['arbitraje_intermedio'], detalle['arbitraje_punta']][i]
        with [col1, col2, col3][i]:
            st.markdown(tarjeta_arbitraje_html(periodo, valor), unsafe_allow_html=True)
    with col4:
        st.markdown(tarjeta_arbitraje_html('', detalle['arbitraje_total'], es_total=True), unsafe_allow_html=True)

def tab_analisis(df, prefijo):
    if 'DATETIME' not in df.columns:
        df = df.copy()
        df['DATETIME'] = pd.to_datetime(df['FECHA_HORA'], format='%d/%m/%Y %H:%M')

    col_con = f'IUSA_CON_BESS_{prefijo}_kW_DEM_15min'
    col_sin = f'IUSA_SIN_BESS_{prefijo}_kW_DEM_15min'

    fecha_min = df['DATETIME'].min().date()
    fecha_max = df['DATETIME'].max().date()
    fecha_def = datetime.now().date() - timedelta(days=1)
    fecha_def = max(fecha_min, min(fecha_def, fecha_max))

    fecha_sel = render_selector_fecha_unica(
        'Análisis',
        'Fecha de corte para demanda del día y acumulados mensuales.',
        'Fecha de corte',
        fecha_def,
        fecha_min,
        fecha_max,
        key=f"fecha_analisis_{prefijo}",
    )

    estado_bess = estado_datos_sin_bess(prefijo)
    mostrar_aviso_sin_bess(estado_bess)

    fecha_str = fecha_sel.strftime('%d/%m/%Y')
    mes_label = fecha_sel.strftime('%m/%Y')
    df_dia = df[df['DATETIME'].dt.date == fecha_sel].copy()
    if df_dia.empty:
        st.warning(f"No hay datos para la fecha {fecha_str}")
        return

    tarifas = cargar_tarifas()
    mes_num = fecha_sel.month
    res_energia_con = calcular_costo_energia_mes(fecha_sel, prefijo, con_bess=True, tarifas=tarifas)
    res_energia_sin = (
        calcular_costo_energia_mes(fecha_sel, prefijo, con_bess=False, tarifas=tarifas)
        if estado_bess['energia'] else None
    )
    demanda_punta_sin = obtener_demanda_rolada_punta(fecha_sel, prefijo, con_bess=False)
    res_cfe_con = calcular_criterio_cfe(fecha_sel, prefijo, con_bess=True, tarifas=tarifas)
    res_cfe_sin = (
        calcular_criterio_cfe(fecha_sel, prefijo, con_bess=False, tarifas=tarifas)
        if demanda_punta_sin is not None else None
    )
    precio_cap = tarifas.get('Capacidad', {}).get(mes_num, 0)

    tab_dem, tab_ene, tab_cfe = st.tabs(["Demanda", "Energía y costos", "Capacidad CFE"])

    with tab_dem:
        df_dem = df_dia.copy()
        if col_con in df_dem.columns:
            df_dem[col_con] = pd.to_numeric(df_dem[col_con], errors='coerce')
        if col_sin in df_dem.columns:
            df_dem[col_sin] = pd.to_numeric(df_dem[col_sin], errors='coerce')
        df_dem_valid = df_dem.dropna(subset=[col_con, col_sin], how='any')

        section_header(
            f"Demanda del día · {fecha_str}",
            'Curva con y sin BESS en intervalos de 15 minutos.',
        )
        if df_dem_valid.empty:
            st.warning(f"No hay lecturas de demanda (15 min) para el {fecha_str}")
        else:
            with st.container(border=True):
                fig = graficar_demanda_dia(df_dia, prefijo, f"Demanda · {fecha_str}")
                st.plotly_chart(fig, use_container_width=True, config={'displayModeBar': False})

        section_header(
            f"Demanda máxima del mes · {mes_label}",
            'Acumulado mensual hasta la fecha de corte.',
        )
        df_dem_mes = construir_tabla_demanda_max_mes(fecha_sel, prefijo)
        if df_dem_mes is not None:
            st.dataframe(
                estilizar_tabla_demanda_periodo(df_dem_mes),
                use_container_width=True,
                hide_index=True,
            )
        else:
            st.warning(f"No hay demanda acumulada para el mes {mes_label}")

    with tab_ene:
        section_header(
            f"Costo de energía por periodo · {mes_label}",
            'kWh acumulados redondeados × tarifa por periodo (Base, Intermedio, Punta).',
        )
        if res_energia_con is None:
            st.warning(f"No hay energía acumulada para el mes {mes_label}")
        elif res_energia_sin is None:
            col_e1, col_e2, col_e3 = st.columns(3)
            with col_e1:
                st.metric("Energía acumulada (con BESS)", f"{fmt_kwh(res_energia_con['total_kwh'])} kWh")
            with col_e2:
                st.metric("Días transcurridos", res_energia_con['dias_mes'])
            with col_e3:
                st.metric("Costo acumulado (con BESS)", f"${res_energia_con['total_mxn']:,.2f}")
        else:
            st.markdown(
                f"""<div class="cap-tarifa">
                Días transcurridos: <b>{res_energia_con['dias_mes']}</b> ·
                Fuente: <b>ENERGIA_{prefijo}_POR_DIA.csv</b>
                </div>""",
                unsafe_allow_html=True,
            )
            st.markdown(
                html_comparacion_costo_energia(res_energia_con, res_energia_sin, tarifas, mes_num),
                unsafe_allow_html=True,
            )
            df_costo_energia = construir_tabla_costo_energia(res_energia_con, res_energia_sin)
            st.dataframe(df_costo_energia, use_container_width=True, hide_index=True)
            with st.container(border=True):
                fig_energia = graficar_costo_energia_periodo(res_energia_con, res_energia_sin)
                st.plotly_chart(fig_energia, use_container_width=True, config={'displayModeBar': False})

    with tab_cfe:
        section_header(
            f"Capacidad CFE · {mes_label}",
            'Capacidad = min(demanda punta, DemandaCalculadaCFE). '
            'DemandaCalculadaCFE = Energía / (0.74 × 24 × días transcurridos).',
        )
        if res_cfe_con is None:
            st.warning(f"No hay datos para calcular capacidad al {fecha_str}")
        elif res_cfe_sin is None:
            col_cap1, col_cap2, col_cap3 = st.columns(3)
            with col_cap1:
                st.metric("Capacidad CFE (con BESS)", f"{res_cfe_con['capacidad_kw']:,} kW")
            with col_cap2:
                st.metric("Tarifa capacidad", f"${precio_cap:,.2f}")
            with col_cap3:
                st.metric("Costo capacidad (con BESS)", f"${res_cfe_con['costo_mxn']:,.2f}")
        else:
            ahorro_cap = res_cfe_sin['costo_mxn'] - res_cfe_con['costo_mxn']
            st.markdown(
                html_comparacion_capacidad(
                    res_cfe_con, res_cfe_sin, precio_cap, ahorro_cap,
                ),
                unsafe_allow_html=True,
            )

        if res_cfe_con is not None:
            dias = res_cfe_con['dias_mes']
            pp_con = res_cfe_con.get('energia_por_periodo', {})
            detalle_con = (
                f"Con BESS: {fmt_kwh(res_cfe_con['energia_kwh'])} kWh "
                f"(Base {fmt_kwh(pp_con.get('base', 0))} · "
                f"Intermedio {fmt_kwh(pp_con.get('intermedio', 0))} · "
                f"Punta {fmt_kwh(pp_con.get('punta', 0))})"
            )
            detalle_sin = ''
            if res_cfe_sin is not None:
                pp_sin = res_cfe_sin.get('energia_por_periodo', {})
                detalle_sin = (
                    f" · Sin BESS: {fmt_kwh(res_cfe_sin['energia_kwh'])} kWh "
                    f"(Base {fmt_kwh(pp_sin.get('base', 0))} · "
                    f"Intermedio {fmt_kwh(pp_sin.get('intermedio', 0))} · "
                    f"Punta {fmt_kwh(pp_sin.get('punta', 0))})"
                )
            st.markdown(
                f"""<div class="cap-tarifa">
                Días transcurridos: <b>{dias}</b> ·
                Fuente: <b>ENERGIA_{prefijo}_POR_DIA.csv</b><br>
                {detalle_con}{detalle_sin}<br>
                Tarifa capacidad: <b>${res_cfe_con['precio_cap']:,.2f}</b>
                </div>""",
                unsafe_allow_html=True,
            )
            df_cfe = construir_tabla_criterio_cfe(res_cfe_con, res_cfe_sin)
            if df_cfe is not None:
                st.dataframe(df_cfe, use_container_width=True, hide_index=True)
            with st.container(border=True):
                fig_cfe = graficar_criterio_cfe(res_cfe_con, res_cfe_sin)
                st.plotly_chart(fig_cfe, use_container_width=True, config={'displayModeBar': False})

def _mtime_fuente_reporte(prefijo):
    ruta = os.path.join(DIRECTORIO_REPORTES, f'COMBINADO_POR_MINUTO_{prefijo}.csv')
    return os.path.getmtime(ruta) if os.path.exists(ruta) else 0

@st.cache_data(show_spinner="Generando reporte PDF...")
def _pdf_bytes_descarga(fecha_str, prefijo, _mtime_fuente):
    from bess_core import generar_reporte_pdf
    exito, ruta = generar_reporte_pdf(fecha_str, prefijo)
    if not exito:
        raise RuntimeError(ruta)
    with open(ruta, 'rb') as f:
        return f.read(), os.path.basename(ruta)

def _render_boton_descarga_archivo(archivo_bytes, nombre_archivo, mime_type, etiqueta, altura=76):
    """Botón de descarga en iframe para evitar estilos de enlace de Streamlit."""
    archivo_b64 = base64.b64encode(archivo_bytes).decode()
    nombre_seguro = html.escape(nombre_archivo, quote=True)
    etiqueta_segura = html.escape(etiqueta)
    components.html(
        f"""
        <!DOCTYPE html>
        <html>
        <head>
        <meta charset="utf-8">
        <style>
            html, body {{
                margin: 0;
                padding: 0;
                background: transparent;
                font-family: "Source Sans Pro", sans-serif;
            }}
            .reporte-dl-box {{
                max-width: 320px;
                margin: 12px auto 0;
                background: linear-gradient(135deg, #1e8449 0%, #27ae60 100%);
                padding: 10px 14px;
                border-radius: 10px;
                text-align: center;
                box-shadow: 0 2px 8px rgba(39, 174, 96, 0.28);
            }}
            .reporte-dl-btn,
            .reporte-dl-btn:link,
            .reporte-dl-btn:visited,
            .reporte-dl-btn:hover,
            .reporte-dl-btn:active {{
                display: block;
                width: 100%;
                box-sizing: border-box;
                background: #ffffff;
                color: #000000;
                padding: 0.55rem 0.85rem;
                border-radius: 6px;
                font-weight: 700;
                font-size: 1.05rem;
                text-decoration: none;
                text-align: center;
                line-height: 1.35;
            }}
            .reporte-dl-btn:hover {{
                background: #eafaf1;
            }}
        </style>
        </head>
        <body>
        <div class="reporte-dl-box">
            <a class="reporte-dl-btn"
               href="data:{mime_type};base64,{archivo_b64}"
               download="{nombre_seguro}">
                {etiqueta_segura}
            </a>
        </div>
        </body>
        </html>
        """,
        height=altura,
    )

def _render_boton_descarga_pdf(pdf_bytes, pdf_name):
    _render_boton_descarga_archivo(
        pdf_bytes,
        pdf_name,
        mime_type='application/pdf',
        etiqueta='Generar Reporte Diario',
    )

def tab_reporte(df, prefijo):
    """Vista previa y generación del reporte PDF diario."""
    if df is None or len(df) == 0:
        st.warning("No hay datos disponibles para generar reportes")
        return

    if 'DATETIME' not in df.columns:
        df['DATETIME'] = pd.to_datetime(df['FECHA_HORA'], format='%d/%m/%Y %H:%M')

    fecha_min = df['DATETIME'].min().date()
    fecha_max = df['DATETIME'].max().date()
    fecha_por_defecto = datetime.now().date() - timedelta(days=1)
    fecha_por_defecto = max(fecha_min, min(fecha_por_defecto, fecha_max))

    fecha_seleccionada = render_selector_fecha_unica(
        'Reporte diario',
        'PDF con perfil de carga, consumo acumulado del mes y arbitraje del día.',
        'Fecha del reporte',
        fecha_por_defecto,
        fecha_min,
        fecha_max,
        key=f"fecha_reporte_pdf_calendario_{prefijo}",
    )

    fecha_str = fecha_seleccionada.strftime('%d/%m/%Y')
    df_dia = df[df['DATETIME'].dt.date == fecha_seleccionada].copy()
    if df_dia.empty:
        st.warning(f"No hay datos para la fecha {fecha_str}")
        return

    tarifas = cargar_tarifas()
    from bess_core import calcular_arbitraje_dia

    detalle = calcular_detalle_energia_periodo(fecha_seleccionada, fecha_seleccionada, prefijo)
    arb_dia = calcular_arbitraje_dia(fecha_str, prefijo, tarifas=tarifas)

    carga_dia = sumar_energia(df_dia['KWH_REC_BESS'])
    descarga_dia = sumar_energia(df_dia['KWH_ENT_BESS'])
    eficiencia = (descarga_dia / carga_dia * 100) if carga_dia > 0 else 0

    with st.container(border=True):
        section_header(f'Resumen del día · {fecha_str}')
        col1, col2, col3, col4 = st.columns(4)
        with col1:
            st.markdown(f"""
            <div class="metric-card" style="border-top:3px solid {COLORES['carga']};">
                <div class="label">Carga BESS</div>
                <div class="value">{fmt_kwh(carga_dia)}</div>
                <div class="sub">kWh del día</div>
            </div>
            """, unsafe_allow_html=True)
        with col2:
            st.markdown(f"""
            <div class="metric-card" style="border-top:3px solid {COLORES['descarga']};">
                <div class="label">Descarga BESS</div>
                <div class="value">{fmt_kwh(descarga_dia)}</div>
                <div class="sub">kWh del día</div>
            </div>
            """, unsafe_allow_html=True)
        with col3:
            st.markdown(f"""
            <div class="metric-card" style="border-top:3px solid {COLORES['primary']};">
                <div class="label">Eficiencia</div>
                <div class="value">{eficiencia:.1f}%</div>
                <div class="sub">{'Óptima' if eficiencia >= 80 else 'Revisar'}</div>
            </div>
            """, unsafe_allow_html=True)
        with col4:
            st.markdown(f"""
            <div class="metric-card" style="border-top:3px solid {COLORES['success']};">
                <div class="label">Arbitraje del día</div>
                <div class="value">${arb_dia['total']:,.2f}</div>
                <div class="sub">MXN</div>
            </div>
            """, unsafe_allow_html=True)

    with st.container(border=True):
        section_header(
            'Vista previa del PDF',
            'Gráfica y tabla con el mismo contenido que se exportará al reporte.',
            compact=True,
        )
        fig_perfil = graficar_perfil(df_dia, prefijo, f'Perfil de carga · {fecha_str}')
        st.plotly_chart(fig_perfil, use_container_width=True, config={'displayModeBar': False})

    with st.container(border=True):
        section_header(
            'Detalle de energía',
            f'Acumulado mensual al {fecha_str} · arbitraje del día.',
            compact=True,
        )
        st.dataframe(
            estilizar_tabla_energia(detalle['df_tabla']),
            use_container_width=True,
            hide_index=True,
        )

        section_header(f'Arbitraje del día · {fecha_str}', compact=True)
        col_a1, col_a2, col_a3, col_a4 = st.columns(4)
        for i, periodo in enumerate(['Base', 'Intermedio', 'Punta']):
            valor = [arb_dia['base'], arb_dia['intermedio'], arb_dia['punta']][i]
            with [col_a1, col_a2, col_a3][i]:
                st.markdown(tarjeta_arbitraje_html(periodo, valor), unsafe_allow_html=True)
        with col_a4:
            st.markdown(tarjeta_arbitraje_html('', arb_dia['total'], es_total=True), unsafe_allow_html=True)

    try:
        pdf_bytes, pdf_name = _pdf_bytes_descarga(
            fecha_str, prefijo, _mtime_fuente_reporte(prefijo)
        )
        _render_boton_descarga_pdf(pdf_bytes, pdf_name)
    except RuntimeError as e:
        st.error(f"Error al generar el reporte: {e}")

# ========== TENDENCIA ==========
def _cargar_energia_diaria_rango(prefijo, fecha_inicio, fecha_fin):
    ruta = os.path.join(DIRECTORIO_REPORTES, f'ENERGIA_{prefijo}_POR_DIA.csv')
    if not os.path.exists(ruta):
        return None
    df = pd.read_csv(ruta)
    df['FECHA_DT'] = pd.to_datetime(df['FECHA'], format='%d/%m/%Y')
    mask = (df['FECHA_DT'].dt.date >= fecha_inicio) & (df['FECHA_DT'].dt.date <= fecha_fin)
    df = df[mask].sort_values('FECHA_DT').reset_index(drop=True)
    if df.empty:
        return None
    df['TOTAL_CON'] = (
        pd.to_numeric(df['BASE_REC'], errors='coerce').fillna(0)
        + pd.to_numeric(df['INTERMEDIO_REC'], errors='coerce').fillna(0)
        + pd.to_numeric(df['PUNTA_REC'], errors='coerce').fillna(0)
    )
    if energia_diaria_tiene_sin_bess(prefijo):
        df['TOTAL_SIN'] = (
            pd.to_numeric(df['BASE_REC_SIN_BESS'], errors='coerce').fillna(0)
            + pd.to_numeric(df['INTERMEDIO_REC_SIN_BESS'], errors='coerce').fillna(0)
            + pd.to_numeric(df['PUNTA_REC_SIN_BESS'], errors='coerce').fillna(0)
        )
    return df

def _cargar_bess_diaria_rango(fecha_inicio, fecha_fin):
    ruta = os.path.join(DIRECTORIO_REPORTES, 'ENERGIA_BESS_POR_DIA.csv')
    if not os.path.exists(ruta):
        return None
    df = pd.read_csv(ruta)
    df['FECHA_DT'] = pd.to_datetime(df['FECHA'], format='%d/%m/%Y')
    mask = (df['FECHA_DT'].dt.date >= fecha_inicio) & (df['FECHA_DT'].dt.date <= fecha_fin)
    df = df[mask].sort_values('FECHA_DT').reset_index(drop=True)
    return df if not df.empty else None

def construir_serie_arbitraje_diaria(df_med, prefijo, tarifas=None):
    from bess_core import calcular_arbitraje_dia
    if tarifas is None:
        tarifas = cargar_tarifas()
    df = df_med.copy()
    df['ARBITRAJE_MXN'] = [
        calcular_arbitraje_dia(fecha, prefijo, tarifas)['total']
        for fecha in df['FECHA']
    ]
    return df

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

def graficar_tendencia_consumo_periodo(df, rango_label):
    fig = go.Figure()
    cols = [
        ('BASE_REC', 'Base', COLORES['base']),
        ('INTERMEDIO_REC', 'Intermedio', COLORES['intermedio']),
        ('PUNTA_REC', 'Punta', COLORES['punta']),
    ]
    for col, lbl, color in cols:
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
        pd.to_numeric(df[c[0]], errors='coerce').fillna(0) for c in cols
    )
    y_max = float(total_diario.max()) if len(total_diario) else 0
    yaxis_range = [0, y_max * 1.08] if y_max > 0 else None
    return _aplicar_estilo_grafica_tendencia(
        fig, f'Consumo diario por periodo · {rango_label}', 'kWh', yaxis_range=yaxis_range,
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

LEYENDA_DIA_ARBITRAJE = (
    ('día laboral', 'Lun–vie', COLORES['success']),
    ('sábado', 'Sábado', COLORES['secondary']),
    ('domingo_festivo', 'Domingo / Festivo', COLORES['danger']),
)

def _tipo_dia_arbitraje(fecha_dt):
    """Clasifica el día para colorear barras de arbitraje."""
    from bess_core import es_festivo
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

def tab_tendencia(df, prefijo):
    with st.container(border=True):
        fecha_inicio, fecha_fin, _ = render_selector_rango(
            df, prefijo, key_suffix='tendencia'
        )

    if fecha_fin < fecha_inicio:
        st.warning("La fecha final debe ser posterior o igual a la inicial")
        return

    rango_label = f"{fecha_inicio.strftime('%d/%m/%Y')} al {fecha_fin.strftime('%d/%m/%Y')}"
    dias = (fecha_fin - fecha_inicio).days + 1

    section_header(f'Tendencia · {rango_label}')

    df_med = _cargar_energia_diaria_rango(prefijo, fecha_inicio, fecha_fin)
    if df_med is None:
        st.warning(f"No hay datos de energía para el periodo {rango_label}")
        return

    df_bess = _cargar_bess_diaria_rango(fecha_inicio, fecha_fin)
    estado_bess = estado_datos_sin_bess(prefijo)
    mostrar_aviso_sin_bess(estado_bess)

    tarifas = cargar_tarifas()
    df_arb = construir_serie_arbitraje_diaria(df_med, prefijo, tarifas)

    total_con = sumar_energia(df_med['TOTAL_CON'])
    arbitraje_acum = sumar_energia(df_arb['ARBITRAJE_MXN'])
    carga_tot = descarga_tot = 0.0
    if df_bess is not None:
        carga_tot = sumar_energia(
            pd.to_numeric(df_bess['BASE_REC'], errors='coerce').fillna(0)
            + pd.to_numeric(df_bess['INTERMEDIO_REC'], errors='coerce').fillna(0)
            + pd.to_numeric(df_bess['PUNTA_REC'], errors='coerce').fillna(0)
        )
        descarga_tot = sumar_energia(
            pd.to_numeric(df_bess['BASE_ENT'], errors='coerce').fillna(0)
            + pd.to_numeric(df_bess['INTERMEDIO_ENT'], errors='coerce').fillna(0)
            + pd.to_numeric(df_bess['PUNTA_ENT'], errors='coerce').fillna(0)
        )

    with st.container(border=True):
        section_header('Resumen del periodo', compact=True)
        if estado_bess['energia'] and 'TOTAL_SIN' in df_med.columns:
            total_sin = sumar_energia(df_med['TOTAL_SIN'])
            ahorro_kwh = total_sin - total_con
            col1, col2, col3, col4, col5 = st.columns(5)
            with col1:
                metric_compact('Días', dias)
            with col2:
                metric_compact('Consumo con BESS', f'{fmt_kwh(total_con)} kWh')
            with col3:
                metric_compact('Consumo sin BESS', f'{fmt_kwh(total_sin)} kWh')
            with col4:
                metric_compact('Ahorro energía', f'{fmt_kwh(ahorro_kwh)} kWh')
            with col5:
                metric_compact('Arbitraje acum.', f'${arbitraje_acum:,.2f}')
        else:
            col1, col2, col3, col4 = st.columns(4)
            with col1:
                metric_compact('Días', dias)
            with col2:
                metric_compact('Consumo total', f'{fmt_kwh(total_con)} kWh')
            with col3:
                metric_compact('Carga BESS', f'{fmt_kwh(carga_tot)} kWh')
            with col4:
                metric_compact('Arbitraje acum.', f'${arbitraje_acum:,.2f}')

    tab_con, tab_cmp, tab_ops = st.tabs(['Consumo por periodo', 'Consumo con BESS', 'Operación BESS'])

    with tab_con:
        with st.container(border=True):
            section_header(
                'Consumo diario por periodo tarifario',
                'Barras apiladas Base, Intermedio y Punta.',
            )
            st.plotly_chart(
                graficar_tendencia_consumo_periodo(df_med, rango_label),
                use_container_width=True, config={'displayModeBar': False},
            )

    with tab_cmp:
        with st.container(border=True):
            section_header(
                'Comparativa con y sin BESS',
                'Líneas: consumo diario. Barras (eje derecho): diferencia en kWh.',
            )
            if estado_bess['energia'] and 'TOTAL_SIN' in df_med.columns:
                st.plotly_chart(
                    graficar_tendencia_con_sin_bess(df_med, rango_label),
                    use_container_width=True, config={'displayModeBar': False},
                )
            else:
                st.info('No hay columnas sin BESS en el archivo diario. Procesa los datos para habilitar esta vista.')
        if estado_bess['energia'] and 'TOTAL_SIN' in df_med.columns:
            res_con = calcular_costo_energia_rango(fecha_inicio, fecha_fin, prefijo, True, tarifas)
            res_sin = calcular_costo_energia_rango(fecha_inicio, fecha_fin, prefijo, False, tarifas)
            if res_con and res_sin:
                ahorro_mxn = res_sin['total_mxn'] - res_con['total_mxn']
                c1, c2, c3 = st.columns(3)
                with c1:
                    st.markdown(f"""
                    <div class="metric-card" style="border-top:3px solid {COLORES['success']};">
                        <div class="label">Costo con BESS</div>
                        <div class="value">${res_con['total_mxn']:,.2f}</div>
                        <div class="sub">MXN</div>
                    </div>
                    """, unsafe_allow_html=True)
                with c2:
                    st.markdown(f"""
                    <div class="metric-card" style="border-top:3px solid {COLORES['danger']};">
                        <div class="label">Costo sin BESS</div>
                        <div class="value">${res_sin['total_mxn']:,.2f}</div>
                        <div class="sub">MXN</div>
                    </div>
                    """, unsafe_allow_html=True)
                with c3:
                    st.markdown(f"""
                    <div class="metric-card" style="border-top:3px solid {COLORES['success']};">
                        <div class="label">Ahorro acumulado</div>
                        <div class="value">${ahorro_mxn:,.2f}</div>
                        <div class="sub">MXN</div>
                    </div>
                    """, unsafe_allow_html=True)

    with tab_ops:
        section_header(
            'Operación del BESS',
            'Barras diarias de carga y descarga. Arbitraje diario: verde = lun–vie, azul = sáb, rojo = dom/festivo.',
        )
        if df_bess is not None:
            with st.container(border=True):
                st.plotly_chart(
                    graficar_tendencia_bess_operacion(df_bess, rango_label),
                    use_container_width=True, config={'displayModeBar': False},
                )
        else:
            st.warning('No hay datos en ENERGIA_BESS_POR_DIA.csv para este rango.')
        with st.container(border=True):
            st.plotly_chart(
                graficar_tendencia_arbitraje(df_arb, rango_label),
                use_container_width=True, config={'displayModeBar': False},
            )
        ef = (descarga_tot / carga_tot * 100) if carga_tot > 0 else 0
        c1, c2, c3 = st.columns(3)
        with c1:
            st.markdown(f"""
            <div class="metric-card" style="border-top:3px solid {COLORES['carga']};">
                <div class="label">Carga BESS</div>
                <div class="value">{fmt_kwh(carga_tot)}</div>
                <div class="sub">kWh</div>
            </div>
            """, unsafe_allow_html=True)
        with c2:
            st.markdown(f"""
            <div class="metric-card" style="border-top:3px solid {COLORES['descarga']};">
                <div class="label">Descarga BESS</div>
                <div class="value">{fmt_kwh(descarga_tot)}</div>
                <div class="sub">kWh</div>
            </div>
            """, unsafe_allow_html=True)
        with c3:
            st.markdown(f"""
            <div class="metric-card" style="border-top:3px solid {COLORES['primary']};">
                <div class="label">Eficiencia</div>
                <div class="value">{ef:.1f}%</div>
                <div class="sub">{'Óptima' if ef >= 80 else 'Revisar'}</div>
            </div>
            """, unsafe_allow_html=True)

# ========== MAIN ==========
def main():
    init_session()

    if not st.session_state.get('autenticado', False):
        login()
        return

    aplicar_estilos()
    es_admin = st.session_state.get('rol') == 'admin'

    if es_admin:
        sidebar_admin()
    else:
        sidebar_user()
    _ajustar_sidebar_por_rol(es_admin)
    
    ruta_ion = os.path.join(DIRECTORIO_REPORTES, 'COMBINADO_POR_MINUTO_ION.csv')
    ruta_banco = os.path.join(DIRECTORIO_REPORTES, 'COMBINADO_POR_MINUTO_BANCO.csv')
    
    if not os.path.exists(ruta_ion) and not os.path.exists(ruta_banco):
        st.warning("No hay datos procesados. Contacta al administrador.")
        return

    with st.container(border=True):
        render_barra_superior(es_admin)
        medidor = st.selectbox("Medidor", ["ION", "BANCO"], key="medidor_principal")

    prefijo = 'ION' if medidor == 'ION' else 'BANCO'
    ruta = os.path.join(DIRECTORIO_REPORTES, f'COMBINADO_POR_MINUTO_{prefijo}.csv')

    if not os.path.exists(ruta):
        st.warning(f"No hay datos para {medidor}")
        return

    df = pd.read_csv(ruta)
    df['DATETIME'] = pd.to_datetime(df['FECHA_HORA'], format='%d/%m/%Y %H:%M')

    tabs = st.tabs(["Operación BESS", "Análisis", "Tendencia", "Reporte", "Recibo"])

    with tabs[0]:
        tab_dashboard(df, prefijo, medidor)

    with tabs[1]:
        tab_analisis(df, prefijo)

    with tabs[2]:
        tab_tendencia(df, prefijo)

    with tabs[3]:
        tab_reporte(df, prefijo)

    with tabs[4]:
        tab_recibo(df, prefijo)

if __name__ == "__main__":
    main()