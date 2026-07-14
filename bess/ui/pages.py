"""
BESS - Sistema de Procesamiento y Reportes - Web App
Pestañas del reporteador (Streamlit).
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
import subprocess
import sys
from decimal import Decimal, ROUND_HALF_UP
import streamlit.components.v1 as components

warnings.filterwarnings('ignore')

# ========== CONSTANTES (bess.config) ==========
from bess.config.constants import VERSION
from bess.config.subestaciones import (
    SUBESTACIONES,
    etiqueta_medidor_consumo,
    medidores_facturacion_subestacion,
    nombre_medidor_facturacion_subestacion,
    prefijo_medidor_facturacion_subestacion,
    recurso_generacion_subestacion,
    ruta_acumulados_por_prefijo,
    ruta_combinado_por_prefijo,
    ruta_energia_dia_por_prefijo,
    subestacion_por_id,
    subestacion_por_prefijo,
    soporta_participacion_capacidad,
)
from bess.data.aggregates.generacion import sumar_generacion_por_periodo
from bess.config.paths import (
    DIRECTORIO_BASE,
    DIRECTORIO_FUENTE,
    DIRECTORIO_PROCESADOS,
    DIRECTORIO_TARIFAS,
    nombre_energia_bess_por_dia,
    ruta_energia_bess_por_dia,
)
from bess.config.theme import COLORES, PERIODO_BG
# Imports de módulos extraídos (Fases 7 y 9)
from bess.cfe.capacity import calcular_criterio_cfe, construir_tabla_criterio_cfe
from bess.cfe.arbitrage import calcular_arbitraje_rango
from bess.cfe.daily_data import energia_diaria_tiene_sin_bess
from bess.cfe.energy_month import (
    calcular_costo_energia_mes,
    calcular_costo_energia_rango,
    construir_tabla_costo_energia,
    html_comparacion_costo_energia,
)
from bess.cfe.power_factor import calcular_cargo_fp, calcular_factor_potencia_recibo
from bess.cfe.receipt import (
    construir_datos_recibo_cfe,
    construir_tabla_recibo_completo,
    generar_recibo_pdf_bytes,
    nombre_archivo_recibo,
    render_html_recibo_cfe,
)
from bess.cfe.report_data import (
    _cargar_acumulados,
    _fila_por_fecha,
    acumulados_tiene_demanda_sin_bess,
    dias_transcurridos_mes,
    obtener_demanda_rolada_punta,
)
from bess.config.esquema_tarifa import esquema_tarifa_prefijo, esquema_tarifa_subestacion, factor_cfe_capacidad, usa_netmetering
from bess.core.energia_periodo import (
    df_energia_para_visualizacion,
    kwh_consumo_acum_periodo_fila,
    kwh_ent_acum_periodo_fila,
    kwh_rec_acum_periodo_fila,
    sumar_consumo_por_periodo_df,
    sumar_ent_por_periodo_df,
    sumar_rec_por_periodo_df,
)
from bess.tariffs.loader import cargar_tarifas
from bess.config.users import ETIQUETA_ROL, rol_es_operador, rol_es_superadmin
from bess.ui.auth import get_usuarios, init_session, login, preparar_ui_login, restaurar_ui_app
from bess.ui.components import (
    html_tarifas_sidebar,
    metric_compact,
    obtener_logo_html,
    render_selector_fecha_unica,
    section_header,
    subnav_en_panel,
)
from bess.ui.downloads import render_boton_descarga
from bess.ui.chart_view import render_grafica_plotly
from bess.ui.participacion_tab import tab_participacion_capacidad
from bess.ui.generacion_tab import tab_generacion
from bess.ui.reportes_tab import tab_reportes
from bess.ui.receipt_tab import tab_recibo as _tab_recibo_core
from bess.ui.emisiones_tab import tab_emisiones as _tab_emisiones_core
from bess.ui.sidebar import _ajustar_sidebar_por_rol, sidebar_admin
from bess.ui.styles import aplicar_estilos
from bess.ui.navigation import render_navegacion_principal
from bess.charts import (
    color_periodo,
    graficar_arbitraje,
    graficar_costo_energia_periodo,
    graficar_criterio_cfe,
    graficar_demanda_dia,
    graficar_perfil,
    graficar_tendencia_arbitraje,
    graficar_tendencia_bess_operacion,
    graficar_tendencia_con_sin_bess,
    graficar_tendencia_consumo_periodo,
)

from bess.core.numbers import (
    a_num as _a_num,
    fmt_kwh,
    kwh_para_calculo,
    redondear_arriba_kw,
    redondear_arriba_mxn,
    redondear_kwh,
    redondear_mxn_energia,
    sumar_energia,
)
from bess.core.dates import etiqueta_rango_operativo, mascara_rango_operativo, serie_fecha_operativa

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


def render_barra_superior(rol: str | None):
    """Logo, título y cierre de sesión."""
    logo_html = obtener_logo_html(288)
    usuario = st.session_state.get('usuario', '')
    rol_nombre = get_usuarios().get(usuario, {}).get('nombre', usuario)
    rol_tipo = ETIQUETA_ROL.get(rol or 'user', 'Usuario')
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
            st.session_state["_logout_pendiente"] = True
            st.rerun()


def render_selector_rango(df, prefijo, key_suffix, medidor=None):
    """Selector de rango de fechas y resumen del periodo."""
    if 'DATETIME' not in df.columns:
        df = df.copy()
        df['DATETIME'] = pd.to_datetime(df['FECHA_HORA'], format='%d/%m/%Y %H:%M')

    fecha_min = serie_fecha_operativa(df['DATETIME']).min()
    fecha_max = serie_fecha_operativa(df['DATETIME']).max()
    fecha_def = datetime.now().date() - timedelta(days=1)
    fecha_def = max(fecha_min, min(fecha_def, fecha_max))

    if medidor:
        st.markdown(
            f'<p class="contexto-medidor">Medidor activo: '
            f'<b>{etiqueta_medidor_consumo(medidor)}</b></p>',
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

    mask = mascara_rango_operativo(df, fecha_inicio, fecha_fin)
    df_filtrado = df[mask].copy()

    rango_label = etiqueta_rango_operativo(fecha_inicio, fecha_fin)
    st.markdown(f"""
    <div class="fecha-resumen">
        <b>{len(df_filtrado):,}</b> registros ·
        <b>{len(df_filtrado['FECHA_HORA'].unique()):,}</b> horas ·
        {rango_label}
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

def _fig_arbitraje_periodo(base, intermedio, punta, rango_label):
    return graficar_arbitraje(
        {'arbitraje': {'Base': base, 'Intermedio': intermedio, 'Punta': punta}},
        f'Arbitraje por periodo · {rango_label}',
    )


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

def tab_recibo(df, prefijo):
    _tab_recibo_core(df, prefijo, render_boton_descarga)


def tab_emisiones(df, prefijo):
    _tab_emisiones_core(df, prefijo, render_boton_descarga)

def _fila_por_fecha(df, fecha):
    if df is None:
        return None
    fecha_str = fecha.strftime('%d/%m/%Y')
    filas = df[df['FECHA'] == fecha_str]
    return filas.iloc[0] if len(filas) > 0 else None

def _cargar_acumulados(prefijo):
    ruta_p = ruta_acumulados_por_prefijo(prefijo)
    if not ruta_p or not ruta_p.exists():
        return None
    df = pd.read_csv(ruta_p)
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
    rango_label = etiqueta_rango_operativo(fecha_inicio, fecha_fin)

    ruta_acumulados_p = ruta_acumulados_por_prefijo(prefijo)
    ruta_med_dia_p = ruta_energia_dia_por_prefijo(prefijo)
    ruta_acumulados = str(ruta_acumulados_p) if ruta_acumulados_p else ""
    ruta_med_dia = str(ruta_med_dia_p) if ruta_med_dia_p else ""
    ruta_bess_dia = str(ruta_energia_bess_por_dia(prefijo))

    df_acum = pd.read_csv(ruta_acumulados) if os.path.exists(ruta_acumulados) else None
    fila_acum_fin = _fila_por_fecha(df_acum, fecha_fin)
    esquema = esquema_tarifa_prefijo(prefijo)
    netmetering = usa_netmetering(esquema)
    df_med_rango = None

    if rango_un_dia:
        titulo_tabla = f"Detalle de Energía por Periodo · acumulado al {fecha_fin.strftime('%d/%m/%Y')}"
        lbl_consumo = 'Consumo Mensual (kWh)'
        lbl_rec = 'Energía Recibida Mensual (kWh)'
        lbl_ent = 'Energía Entregada Mensual (kWh)'

        if fila_acum_fin is not None:
            consumo_base = kwh_consumo_acum_periodo_fila(fila_acum_fin, 'base', esquema)
            consumo_intermedio = kwh_consumo_acum_periodo_fila(fila_acum_fin, 'intermedio', esquema)
            consumo_punta = kwh_consumo_acum_periodo_fila(fila_acum_fin, 'punta', esquema)
            if netmetering:
                rec_base = kwh_rec_acum_periodo_fila(fila_acum_fin, 'base')
                rec_intermedio = kwh_rec_acum_periodo_fila(fila_acum_fin, 'intermedio')
                rec_punta = kwh_rec_acum_periodo_fila(fila_acum_fin, 'punta')
                ent_base = kwh_ent_acum_periodo_fila(fila_acum_fin, 'base')
                ent_intermedio = kwh_ent_acum_periodo_fila(fila_acum_fin, 'intermedio')
                ent_punta = kwh_ent_acum_periodo_fila(fila_acum_fin, 'punta')
            demanda_base = redondear_arriba_kw(fila_acum_fin.get('BASE_DEM_CON_BESS_MAX', 0))
            demanda_intermedio = redondear_arriba_kw(fila_acum_fin.get('INTERMEDIO_DEM_CON_BESS_MAX', 0))
            demanda_punta = redondear_arriba_kw(fila_acum_fin.get('PUNTA_DEM_CON_BESS_MAX', 0))
        else:
            consumo_base = consumo_intermedio = consumo_punta = 0
            if netmetering:
                rec_base = rec_intermedio = rec_punta = 0
                ent_base = ent_intermedio = ent_punta = 0
            demanda_base = demanda_intermedio = demanda_punta = 0
    else:
        titulo_tabla = f"Detalle de Energía por Periodo · {rango_label}"
        lbl_consumo = 'Consumo del Periodo (kWh)'
        lbl_rec = 'Energía Recibida del Periodo (kWh)'
        lbl_ent = 'Energía Entregada del Periodo (kWh)'

        if os.path.exists(ruta_med_dia):
            df_med_rango = pd.read_csv(ruta_med_dia)
            df_med_rango['FECHA_DT'] = pd.to_datetime(df_med_rango['FECHA'], format='%d/%m/%Y')
            mask_med = (
                (df_med_rango['FECHA_DT'].dt.date >= fecha_inicio)
                & (df_med_rango['FECHA_DT'].dt.date <= fecha_fin)
            )
            df_med_rango = df_med_rango.loc[mask_med]
            sums_med = sumar_consumo_por_periodo_df(df_med_rango, esquema, con_bess=True)
            if netmetering:
                sums_rec = sumar_rec_por_periodo_df(df_med_rango)
                sums_ent = sumar_ent_por_periodo_df(df_med_rango)
        else:
            sums_med = {'base': 0.0, 'intermedio': 0.0, 'punta': 0.0}
            if netmetering:
                sums_rec = sums_ent = {'base': 0.0, 'intermedio': 0.0, 'punta': 0.0}
        consumo_base = sumar_energia(sums_med['base'])
        consumo_intermedio = sumar_energia(sums_med['intermedio'])
        consumo_punta = sumar_energia(sums_med['punta'])
        if netmetering:
            rec_base = sumar_energia(sums_rec['base'])
            rec_intermedio = sumar_energia(sums_rec['intermedio'])
            rec_punta = sumar_energia(sums_rec['punta'])
            ent_base = sumar_energia(sums_ent['base'])
            ent_intermedio = sumar_energia(sums_ent['intermedio'])
            ent_punta = sumar_energia(sums_ent['punta'])

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

    tarifas = cargar_tarifas(esquema_tarifa_prefijo(prefijo))

    arb = calcular_arbitraje_rango(
        fecha_inicio,
        fecha_fin,
        prefijo,
        carga_base=carga_base,
        carga_intermedio=carga_intermedio,
        carga_punta=carga_punta,
        descarga_base=descarga_base,
        descarga_intermedio=descarga_intermedio,
        descarga_punta=descarga_punta,
        tarifas=tarifas,
    )
    arbitraje_base = arb['base']
    arbitraje_intermedio = arb['intermedio']
    arbitraje_punta = arb['punta']
    arbitraje_total = arb['total']

    c_b, c_i, c_p, c_t = _celdas_kwh_tabla(consumo_base, consumo_intermedio, consumo_punta)
    car_b, car_i, car_p, car_t = _celdas_kwh_tabla(carga_base, carga_intermedio, carga_punta)
    des_b, des_i, des_p, des_t = _celdas_kwh_tabla(descarga_base, descarga_intermedio, descarga_punta)

    data = [['Periodo', 'Base', 'Intermedio', 'Punta', 'Total']]
    data.append([lbl_consumo, c_b, c_i, c_p, c_t])
    if netmetering:
        rec_b, rec_i, rec_p, rec_t = _celdas_kwh_tabla(rec_base, rec_intermedio, rec_punta)
        ent_b, ent_i, ent_p, ent_t = _celdas_kwh_tabla(ent_base, ent_intermedio, ent_punta)
        data.append([lbl_rec, rec_b, rec_i, rec_p, rec_t])
        data.append([lbl_ent, ent_b, ent_i, ent_p, ent_t])
    data.append(['Demanda Rolada (kW)', f'{demanda_base:,}', f'{demanda_intermedio:,}', f'{demanda_punta:,}', f'{demanda_punta:,}'])

    sub = subestacion_por_prefijo(prefijo)
    if sub and soporta_participacion_capacidad(sub.id):
        gen_inicio = fecha_fin.replace(day=1) if rango_un_dia else fecha_inicio
        gen = sumar_generacion_por_periodo(sub.id, gen_inicio, fecha_fin)
        if gen is not None:
            gen_b, gen_i, gen_p, gen_t = _celdas_kwh_tabla(
                sumar_energia(gen['base']),
                sumar_energia(gen['intermedio']),
                sumar_energia(gen['punta']),
            )
            data.append(['Generación Acumulada', gen_b, gen_i, gen_p, gen_t])

    data.append([lbl_carga, car_b, car_i, car_p, car_t])
    data.append([lbl_descarga, des_b, des_i, des_p, des_t])
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

def tab_dashboard(df, prefijo, medidor):
    with st.container(border=True):
        fecha_inicio, fecha_fin, df_filtrado = render_selector_rango(
            df, prefijo, key_suffix='dashboard', medidor=medidor
        )

    if len(df_filtrado) == 0:
        st.warning("No hay datos en el rango seleccionado")
        return

    rango_label = etiqueta_rango_operativo(fecha_inicio, fecha_fin)
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
        render_grafica_plotly(
            fig_perfil,
            f'perfil_{prefijo}_{fecha_inicio:%Y%m%d}_{fecha_fin:%Y%m%d}.png',
            download_key=f'perfil_{prefijo}_{fecha_inicio:%Y%m%d}_{fecha_fin:%Y%m%d}',
        )
        if descarga == 0 and carga > 0:
            st.caption(
                'En el periodo seleccionado hay carga BESS pero no descarga registrada '
                '(valores en cero en KWH_ENT_BESS). Prueba otro día o rango.'
            )
        elif descarga == 0 and carga == 0:
            st.caption('No hay actividad BESS (carga ni descarga) en el periodo seleccionado.')

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

    st.divider()
    section_header('Gráfica de arbitraje')
    fig_arbitraje = _fig_arbitraje_periodo(
        detalle['arbitraje_base'],
        detalle['arbitraje_intermedio'],
        detalle['arbitraje_punta'],
        detalle['rango_label'],
    )
    render_grafica_plotly(
        fig_arbitraje,
        f'arbitraje_{prefijo}_{fecha_inicio:%Y%m%d}_{fecha_fin:%Y%m%d}.png',
        download_key=f'arbitraje_{prefijo}_{fecha_inicio:%Y%m%d}_{fecha_fin:%Y%m%d}',
    )

def tab_analisis(df, prefijo):
    if 'DATETIME' not in df.columns:
        df = df.copy()
        df['DATETIME'] = pd.to_datetime(df['FECHA_HORA'], format='%d/%m/%Y %H:%M')

    col_con = f'IUSA_CON_BESS_{prefijo}_kW_DEM_15min'
    col_sin = f'IUSA_SIN_BESS_{prefijo}_kW_DEM_15min'

    fecha_min = serie_fecha_operativa(df['DATETIME']).min()
    fecha_max = serie_fecha_operativa(df['DATETIME']).max()
    fecha_def = datetime.now().date() - timedelta(days=1)
    fecha_def = max(fecha_min, min(fecha_def, fecha_max))

    fecha_sel = render_selector_fecha_unica(
        'Análisis',
        'Fecha operativa (00:05–00:00) para demanda del día y acumulados mensuales.',
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
    df_dia = df[mascara_rango_operativo(df, fecha_sel, fecha_sel)].copy()
    if df_dia.empty:
        st.warning(f"No hay datos para la fecha {fecha_str}")
        return

    tarifas = cargar_tarifas(esquema_tarifa_prefijo(prefijo))
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

    vista_analisis = subnav_en_panel("Análisis detallado", [
        ("dem", "📈 Demanda"),
        ("ene", "💰 Energía y costos"),
        ("cfe", "🏭 Capacidad CFE"),
    ], f"analisis_vista_{prefijo}")

    if vista_analisis == "dem":
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
                render_grafica_plotly(
                    fig,
                    f'demanda_{prefijo}_{fecha_sel:%Y%m%d}.png',
                    download_key=f'dl_demanda_{prefijo}_{fecha_sel:%Y%m%d}',
                )

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

    elif vista_analisis == "ene":
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
                render_grafica_plotly(
                    fig_energia,
                    f'costo_energia_{prefijo}_{mes_label.replace("/", "-")}.png',
                    download_key=f'dl_energia_{prefijo}_{fecha_sel:%Y%m}',
                )

    elif vista_analisis == "cfe":
        factor_carga = factor_cfe_capacidad(esquema_tarifa_prefijo(prefijo))
        section_header(
            f"Capacidad CFE · {mes_label}",
            'Capacidad = min(demanda punta, DemandaCalculadaCFE). '
            f'DemandaCalculadaCFE = Energía / ({factor_carga} × 24 × días transcurridos).',
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
                render_grafica_plotly(
                    fig_cfe,
                    f'capacidad_cfe_{prefijo}_{mes_label.replace("/", "-")}.png',
                    download_key=f'dl_cfe_{prefijo}_{fecha_sel:%Y%m}',
                )

def _mtime_fuente_reporte(prefijo):
    ruta_p = ruta_combinado_por_prefijo(prefijo)
    return ruta_p.stat().st_mtime if ruta_p and ruta_p.exists() else 0

@st.cache_data(show_spinner="Generando reporte PDF...")
def _pdf_bytes_descarga(fecha_str, prefijo, incluir_generacion, _mtime_fuente):
    from bess_core import generar_reporte_pdf
    exito, ruta = generar_reporte_pdf(
        fecha_str, prefijo, incluir_generacion=incluir_generacion
    )
    if not exito:
        raise RuntimeError(ruta)
    with open(ruta, 'rb') as f:
        return f.read(), os.path.basename(ruta)

def _render_boton_descarga_pdf(pdf_bytes, pdf_name):
    render_boton_descarga(
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

    fecha_min = serie_fecha_operativa(df['DATETIME']).min()
    fecha_max = serie_fecha_operativa(df['DATETIME']).max()
    fecha_por_defecto = datetime.now().date() - timedelta(days=1)
    fecha_por_defecto = max(fecha_min, min(fecha_por_defecto, fecha_max))

    fecha_seleccionada = render_selector_fecha_unica(
        'Reporte diario',
        'PDF con perfil de carga, consumo acumulado del mes y arbitraje del día (00:05–00:00).',
        'Fecha del reporte',
        fecha_por_defecto,
        fecha_min,
        fecha_max,
        key=f"fecha_reporte_pdf_calendario_{prefijo}",
    )

    fecha_str = fecha_seleccionada.strftime('%d/%m/%Y')
    df_dia = df[mascara_rango_operativo(df, fecha_seleccionada, fecha_seleccionada)].copy()
    if df_dia.empty:
        st.warning(f"No hay datos para la fecha {fecha_str}")
        return

    sub = subestacion_por_prefijo(prefijo)
    recurso_gen = recurso_generacion_subestacion(sub.id) if sub else None
    incluir_generacion = True
    if recurso_gen:
        incluir_generacion = st.checkbox(
            f"Incluir generación en el perfil del PDF ({recurso_gen.etiqueta})",
            value=True,
            key=f"pdf_incluir_generacion_{prefijo}",
        )

    tarifas = cargar_tarifas(esquema_tarifa_prefijo(prefijo))
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
        fig_perfil = graficar_perfil(
            df_dia, prefijo, f'Perfil de carga · {fecha_str}', incluir_generacion=incluir_generacion
        )
        render_grafica_plotly(
            fig_perfil,
            f'reporte_perfil_{prefijo}_{fecha_seleccionada:%Y%m%d}.png',
            download_key=f'dl_perfil_reporte_{prefijo}_{fecha_seleccionada:%Y%m%d}',
        )

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
            fecha_str, prefijo, incluir_generacion, _mtime_fuente_reporte(prefijo)
        )
        _render_boton_descarga_pdf(pdf_bytes, pdf_name)
    except RuntimeError as e:
        st.error(f"Error al generar el reporte: {e}")

# ========== TENDENCIA ==========
def _cargar_energia_diaria_rango(prefijo, fecha_inicio, fecha_fin):
    ruta_p = ruta_energia_dia_por_prefijo(prefijo)
    if not ruta_p or not ruta_p.exists():
        return None
    df = pd.read_csv(ruta_p)
    df['FECHA_DT'] = pd.to_datetime(df['FECHA'], format='%d/%m/%Y')
    mask = (df['FECHA_DT'].dt.date >= fecha_inicio) & (df['FECHA_DT'].dt.date <= fecha_fin)
    df = df[mask].sort_values('FECHA_DT').reset_index(drop=True)
    if df.empty:
        return None
    esquema = esquema_tarifa_prefijo(prefijo)
    return df_energia_para_visualizacion(df, esquema)

def _cargar_bess_diaria_rango(fecha_inicio, fecha_fin, prefijo):
    ruta = str(ruta_energia_bess_por_dia(prefijo))
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
        tarifas = cargar_tarifas(esquema_tarifa_prefijo(prefijo))
    df = df_med.copy()
    df['ARBITRAJE_MXN'] = [
        calcular_arbitraje_dia(fecha, prefijo, tarifas)['total']
        for fecha in df['FECHA']
    ]
    return df

def tab_tendencia(df, prefijo):
    with st.container(border=True):
        fecha_inicio, fecha_fin, _ = render_selector_rango(
            df, prefijo, key_suffix='tendencia'
        )

    if fecha_fin < fecha_inicio:
        st.warning("La fecha final debe ser posterior o igual a la inicial")
        return

    rango_label = etiqueta_rango_operativo(fecha_inicio, fecha_fin)
    dias = (fecha_fin - fecha_inicio).days + 1

    section_header(f'Tendencia · {rango_label}')

    df_med = _cargar_energia_diaria_rango(prefijo, fecha_inicio, fecha_fin)
    if df_med is None:
        st.warning(f"No hay datos de energía para el periodo {rango_label}")
        return

    df_bess = _cargar_bess_diaria_rango(fecha_inicio, fecha_fin, prefijo)
    estado_bess = estado_datos_sin_bess(prefijo)
    mostrar_aviso_sin_bess(estado_bess)

    tarifas = cargar_tarifas(esquema_tarifa_prefijo(prefijo))
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

    vista_tendencia = subnav_en_panel("Vistas de tendencia", [
        ("con", "📊 Consumo por periodo"),
        ("cmp", "⚖️ Consumo con BESS"),
        ("ops", "🔋 Operación BESS"),
    ], f"tendencia_vista_{prefijo}")

    if vista_tendencia == "con":
        with st.container(border=True):
            section_header(
                'Consumo diario por periodo tarifario',
                'Barras apiladas Base, Intermedio y Punta.',
            )
            render_grafica_plotly(
                graficar_tendencia_consumo_periodo(df_med, rango_label),
                f'tendencia_consumo_{prefijo}_{fecha_inicio:%Y%m%d}_{fecha_fin:%Y%m%d}.png',
                download_key=f'dl_tend_con_{prefijo}_{fecha_inicio:%Y%m%d}_{fecha_fin:%Y%m%d}',
            )

    elif vista_tendencia == "cmp":
        with st.container(border=True):
            section_header(
                'Comparativa con y sin BESS',
                'Líneas: consumo diario. Barras (eje derecho): diferencia en kWh.',
            )
            if estado_bess['energia'] and 'TOTAL_SIN' in df_med.columns:
                render_grafica_plotly(
                    graficar_tendencia_con_sin_bess(df_med, rango_label),
                    f'tendencia_con_sin_bess_{prefijo}_{fecha_inicio:%Y%m%d}_{fecha_fin:%Y%m%d}.png',
                    download_key=f'dl_tend_cmp_{prefijo}_{fecha_inicio:%Y%m%d}_{fecha_fin:%Y%m%d}',
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

    elif vista_tendencia == "ops":
        section_header(
            'Operación del BESS',
            'Barras diarias de carga y descarga. Arbitraje diario: verde = lun–vie, azul = sáb, rojo = dom/festivo.',
        )
        if df_bess is not None:
            with st.container(border=True):
                render_grafica_plotly(
                    graficar_tendencia_bess_operacion(df_bess, rango_label),
                    f'tendencia_bess_{prefijo}_{fecha_inicio:%Y%m%d}_{fecha_fin:%Y%m%d}.png',
                    download_key=f'dl_tend_ops_{prefijo}_{fecha_inicio:%Y%m%d}_{fecha_fin:%Y%m%d}',
                )
        else:
            st.warning(
                f'No hay datos en {nombre_energia_bess_por_dia(prefijo)} para este rango.'
            )
        with st.container(border=True):
            render_grafica_plotly(
                graficar_tendencia_arbitraje(df_arb, rango_label),
                f'tendencia_arbitraje_{prefijo}_{fecha_inicio:%Y%m%d}_{fecha_fin:%Y%m%d}.png',
                download_key=f'dl_tend_arb_{prefijo}_{fecha_inicio:%Y%m%d}_{fecha_fin:%Y%m%d}',
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
def _bloque_reporteador(prefijo, medidor):
    """Navegación + contenido principal."""
    if not st.session_state.get('autenticado', False):
        return

    from streamlit_autorefresh import st_autorefresh
    st_autorefresh(interval=15 * 60 * 1000, key="autorefresh_datos")

    ruta_p = ruta_combinado_por_prefijo(prefijo)
    if not ruta_p or not ruta_p.exists():
        from bess.config.users import rol_es_operador
        from bess.ui.pipeline_status import evaluar_pipeline, render_estado_vacio_reporteador

        if rol_es_operador(st.session_state.get("rol")):
            render_estado_vacio_reporteador(evaluar_pipeline())
        else:
            st.warning(
                f"No hay datos para {etiqueta_medidor_consumo(medidor)}. "
                "Contacte al administrador."
            )
        return

    df = pd.read_csv(ruta_p)
    df['DATETIME'] = pd.to_datetime(df['FECHA_HORA'], format='%d/%m/%Y %H:%M')

    sub_id = st.session_state.get("subestacion_principal")
    seccion = render_navegacion_principal(sub_id)

    if seccion == "operacion":
        tab_dashboard(df, prefijo, medidor)
    elif seccion == "analisis":
        tab_analisis(df, prefijo)
    elif seccion == "participacion":
        sub_id = st.session_state.get("subestacion_principal", "")
        tab_participacion_capacidad(df, sub_id)
    elif seccion == "tendencia":
        tab_tendencia(df, prefijo)
    elif seccion == "generacion":
        sub_id = st.session_state.get("subestacion_principal", "")
        tab_generacion(sub_id)
    elif seccion in ("reporte", "reportes"):
        tab_reportes(df, prefijo, tab_reporte)
    elif seccion == "recibo":
        tab_recibo(df, prefijo)
    elif seccion == "emisiones":
        tab_emisiones(df, prefijo)


def _al_cambiar_subestacion():
    sub_id = st.session_state.get("subestacion_principal")
    default = nombre_medidor_facturacion_subestacion(sub_id)
    opciones = medidores_facturacion_subestacion(sub_id)
    if default:
        st.session_state["medidor_principal"] = default
    elif opciones:
        st.session_state["medidor_principal"] = opciones[0]


def _normalizar_medidor_sesion():
    """Convierte IDs legacy de sesión al nombre del catálogo (= medidor_id en BD)."""
    from bess.data.ingest.medidor_ids import medidor_id_canonico

    actual = st.session_state.get("medidor_principal")
    if not actual:
        return
    canon = medidor_id_canonico(actual)
    sub_id = st.session_state.get("subestacion_principal")
    opciones = medidores_facturacion_subestacion(sub_id) if sub_id else []
    if canon in opciones:
        st.session_state["medidor_principal"] = canon
    elif opciones:
        default = nombre_medidor_facturacion_subestacion(sub_id)
        st.session_state["medidor_principal"] = default or opciones[0]


def main():
    init_session()

    if st.session_state.pop("_logout_pendiente", False):
        st.cache_data.clear()
        st.session_state.autenticado = False
        st.session_state.usuario = None
        st.session_state.rol = None
        st.session_state.pop("seccion_activa", None)
        st.session_state.pop("modo_vista", None)
        st.session_state.pop("sidebar_inicial_aplicada", None)
        st.rerun()

    if not st.session_state.get('autenticado', False):
        preparar_ui_login()
        login_placeholder = st.empty()
        with login_placeholder.container():
            login()
        if not st.session_state.get('autenticado', False):
            return
        login_placeholder.empty()

    rol = st.session_state.get('rol')
    es_operador = rol_es_operador(rol)
    es_superadmin = rol_es_superadmin(rol)
    restaurar_ui_app(restaurar_sidebar=es_operador)
    aplicar_estilos()
    if not es_operador:
        st.markdown('<div class="bess-rol-user" aria-hidden="true"></div>', unsafe_allow_html=True)

    if es_operador:
        sidebar_admin(mostrar_superadmin=es_superadmin)
    _ajustar_sidebar_por_rol(es_operador)

    modo_vista = st.session_state.get("modo_vista")

    if modo_vista == "mantenimiento_db":
        if not es_superadmin:
            st.session_state["modo_vista"] = "reporteador"
            st.warning("Acceso denegado a Mantenimiento DB.")
        else:
            with st.container(border=True):
                render_barra_superior(rol)
            from bess.ui.db_tools.page import main as db_tools_main

            db_tools_main()
            return

    if modo_vista == "admin_catalogo":
        if not es_superadmin:
            st.session_state["modo_vista"] = "reporteador"
            st.warning("Acceso denegado a administración del catálogo.")
        else:
            with st.container(border=True):
                render_barra_superior(rol)
            from bess.ui.catalog_admin.page import main as catalog_admin_main

            catalog_admin_main()
            return
    
    rutas_disponibles = [
        ruta_combinado_por_prefijo(med.nombre)
        for sub in SUBESTACIONES
        for med in sub.medidores_consumo
    ]
    if not any(r and r.exists() for r in rutas_disponibles):
        if es_operador:
            with st.container(border=True):
                render_barra_superior(rol)
            from bess.ui.pipeline_status import evaluar_pipeline, render_estado_vacio_reporteador

            render_estado_vacio_reporteador(evaluar_pipeline())
        else:
            st.warning(
                "No hay datos procesados para consultar. "
                "Contacte al administrador para ejecutar el pipeline."
            )
        return

    if "subestacion_principal" not in st.session_state:
        st.session_state["subestacion_principal"] = SUBESTACIONES[0].id
    if "medidor_principal" not in st.session_state:
        sub_inicial = SUBESTACIONES[0].id
        default = nombre_medidor_facturacion_subestacion(sub_inicial)
        st.session_state["medidor_principal"] = (
            default or SUBESTACIONES[0].medidor_facturacion.nombre
            if SUBESTACIONES[0].medidor_facturacion
            else ""
        )
    _normalizar_medidor_sesion()

    with st.container(border=True):
        render_barra_superior(rol)
        st.markdown(
            '<div class="panel-medidor">'
            '<p class="panel-medidor-label">Subestación</p>'
            '</div>',
            unsafe_allow_html=True,
        )
        opciones_sub = [s.id for s in SUBESTACIONES]
        st.selectbox(
            "Subestación",
            opciones_sub,
            key="subestacion_principal",
            label_visibility="collapsed",
            format_func=lambda sid: (
                subestacion_por_id(sid).nombre if subestacion_por_id(sid) else sid
            ),
            on_change=_al_cambiar_subestacion,
        )
        st.markdown(
            '<div class="panel-medidor">'
            '<p class="panel-medidor-label">Medidor de Facturación</p>'
            '</div>',
            unsafe_allow_html=True,
        )
        sub_actual = subestacion_por_id(st.session_state.get("subestacion_principal"))
        opciones_medidor = (
            medidores_facturacion_subestacion(st.session_state.get("subestacion_principal"))
            if sub_actual
            else []
        )
        medidor = st.selectbox(
            "Medidor",
            opciones_medidor,
            key="medidor_principal",
            label_visibility="collapsed",
            format_func=lambda mid: etiqueta_medidor_consumo(mid),
        )

    prefijo = medidor
    _bloque_reporteador(prefijo, medidor)

if __name__ == "__main__":
    main()