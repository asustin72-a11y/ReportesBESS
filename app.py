"""
BESS - Sistema de Procesamiento y Reportes - Web App
Versión con gráficas de alta calidad
"""

import streamlit as st
import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
import matplotlib.dates as mdates
import seaborn as sns
import os
from datetime import datetime, timedelta
import warnings
import io
import base64

# Configuración de la página
st.set_page_config(
    page_title="BESS - Sistema de Energía",
    page_icon="⚡",
    layout="wide",
    initial_sidebar_state="expanded"
)

warnings.filterwarnings('ignore')

# Importar estilos
from styles import (
    configurar_estilo_profesional, 
    crear_figura, 
    aplicar_estilo_ax,
    COLORES_BESS,
    colores_periodo,
    formatear_kw,
    formatear_kwh
)

# Aplicar estilos
configurar_estilo_profesional()

# ========== CONFIGURACIÓN GLOBAL ==========
DIRECTORIO_BASE = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'data')
DIRECTORIO_FUENTE = os.path.join(DIRECTORIO_BASE, 'ArchivosFuente')
DIRECTORIO_PROCESADOS = os.path.join(DIRECTORIO_BASE, 'ArchivosProcesados')
DIRECTORIO_REPORTES = os.path.join(DIRECTORIO_BASE, 'ArchivosReporte')
DIRECTORIO_REPORTES_DIARIOS = os.path.join(DIRECTORIO_BASE, 'ReportesDiarios')
DIRECTORIO_TARIFAS = os.path.join(DIRECTORIO_BASE, 'Tarifas')

# Crear directorios
for dir_path in [DIRECTORIO_BASE, DIRECTORIO_FUENTE, DIRECTORIO_PROCESADOS,
                 DIRECTORIO_REPORTES, DIRECTORIO_REPORTES_DIARIOS, DIRECTORIO_TARIFAS]:
    os.makedirs(dir_path, exist_ok=True)

# ========== FUNCIONES DE PROCESAMIENTO ==========

def cargar_tarifas():
    ruta_tarifas = os.path.join(DIRECTORIO_TARIFAS, 'Tarifas_2026.csv')
    if not os.path.exists(ruta_tarifas):
        return {'Base': {i: 0 for i in range(1, 13)}, 'Intermedio': {i: 0 for i in range(1, 13)}, 'Punta': {i: 0 for i in range(1, 13)}}
    try:
        df_tarifas = pd.read_csv(ruta_tarifas)
        tarifas = {'Base': {}, 'Intermedio': {}, 'Punta': {}}
        for _, row in df_tarifas.iterrows():
            tipo = row['Tarifa'].strip()
            if tipo not in tarifas:
                continue
            for mes in range(1, 13):
                col_mes = str(mes)
                if col_mes in df_tarifas.columns:
                    try:
                        tarifas[tipo][mes] = float(row[col_mes])
                    except (ValueError, TypeError):
                        tarifas[tipo][mes] = 0
                else:
                    tarifas[tipo][mes] = 0
        for tipo in tarifas:
            for mes in range(1, 13):
                if mes not in tarifas[tipo]:
                    tarifas[tipo][mes] = 0
        return tarifas
    except Exception as e:
        return {'Base': {i: 0 for i in range(1, 13)}, 'Intermedio': {i: 0 for i in range(1, 13)}, 'Punta': {i: 0 for i in range(1, 13)}}

def get_mes_espanol(mes_numero):
    meses = {1: 'Enero', 2: 'Febrero', 3: 'Marzo', 4: 'Abril', 5: 'Mayo', 6: 'Junio',
             7: 'Julio', 8: 'Agosto', 9: 'Septiembre', 10: 'Octubre', 11: 'Noviembre', 12: 'Diciembre'}
    return meses.get(mes_numero, '')

# ========== FUNCIONES DE GRÁFICAS MEJORADAS ==========

def graficar_comparacion_iusa(datos_dia, prefijo, fecha_seleccionada):
    """Gráfica de comparación IUSA con estilo profesional"""
    
    # Verificar datos
    col_iusa_con = f'IUSA_CON_BESS_{prefijo}_kW'
    col_iusa_sin = f'IUSA_SIN_BESS_{prefijo}_kW'
    
    if col_iusa_con not in datos_dia.columns or col_iusa_sin not in datos_dia.columns:
        fig, ax = plt.subplots(figsize=(12, 5), facecolor='#f8f9fa')
        ax.text(0.5, 0.5, 'Datos no disponibles', transform=ax.transAxes,
                ha='center', va='center', fontsize=14, color='#95a5a6')
        ax.set_facecolor('#ffffff')
        plt.close()
        return fig
    
    # Crear figura
    fig, ax = plt.subplots(figsize=(14, 5.5), facecolor='#f8f9fa')
    ax.set_facecolor('#ffffff')
    
    # Preparar datos
    horas = datos_dia['DATETIME'].values
    iusa_con = datos_dia[col_iusa_con].values
    iusa_sin = datos_dia[col_iusa_sin].values
    
    # Estilo de líneas
    line_width = 2.8
    
    # Área sombreada (con transparencia)
    ax.fill_between(horas, 0, iusa_con, alpha=0.15, color=COLORES_BESS['primary'], label='_nolegend_')
    ax.fill_between(horas, 0, iusa_sin, alpha=0.12, color=COLORES_BESS['warning'], label='_nolegend_')
    
    # Líneas principales
    ax.plot(horas, iusa_con, 
            color=COLORES_BESS['primary'], 
            linewidth=line_width,
            marker='o',
            markersize=4,
            markeredgecolor='white',
            markeredgewidth=1.5,
            label='IUSA Con BESS')
    
    ax.plot(horas, iusa_sin, 
            color=COLORES_BESS['warning'], 
            linewidth=line_width,
            linestyle='--',
            marker='s',
            markersize=4,
            markeredgecolor='white',
            markeredgewidth=1.5,
            label='IUSA Sin BESS')
    
    # Configurar ejes
    ax.xaxis.set_major_formatter(mdates.DateFormatter('%H:%M'))
    ax.xaxis.set_major_locator(mdates.HourLocator(interval=2))
    ax.xaxis.set_minor_locator(mdates.HourLocator(interval=1))
    
    # Estilo profesional
    aplicar_estilo_ax(
        ax,
        titulo=f'Comparación IUSA - {fecha_seleccionada}',
        xlabel='Hora del día',
        ylabel='Potencia (kW)'
    )
    
    # Línea base
    ax.axhline(y=0, color='#95a5a6', linestyle='-', linewidth=0.8, alpha=0.5)
    
    # Leyenda mejorada
    ax.legend(
        loc='upper right',
        frameon=True,
        facecolor='#ffffff',
        edgecolor='#e2e8f0',
        fontsize=11,
        borderpad=1,
        handlelength=3,
        shadow=True
    )
    
    plt.xticks(rotation=45, ha='right')
    plt.tight_layout()
    
    return fig

def graficar_perfil_carga(datos_dia, prefijo, fecha_seleccionada):
    """Gráfica de perfil de carga con estilo profesional"""
    
    # Verificar datos
    col_medidor_rec = f'{prefijo}_REC_kW'
    
    if col_medidor_rec not in datos_dia.columns:
        fig, ax = plt.subplots(figsize=(12, 5), facecolor='#f8f9fa')
        ax.text(0.5, 0.5, 'Datos no disponibles', transform=ax.transAxes,
                ha='center', va='center', fontsize=14, color='#95a5a6')
        ax.set_facecolor('#ffffff')
        plt.close()
        return fig
    
    # Crear figura
    fig, ax = plt.subplots(figsize=(14, 5.5), facecolor='#f8f9fa')
    ax.set_facecolor('#ffffff')
    
    # Preparar datos
    horas = datos_dia['DATETIME'].values
    medidor_rec = datos_dia[col_medidor_rec].values
    bess_rec = datos_dia['BESS_REC_kW'].values
    bess_ent = -datos_dia['BESS_ENT_kW'].values if 'BESS_ENT_kW' in datos_dia.columns else np.zeros_like(bess_rec)
    
    # Áreas con transparencia
    ax.fill_between(horas, 0, medidor_rec, alpha=0.12, color=COLORES_BESS['primary'], label='_nolegend_')
    ax.fill_between(horas, 0, bess_rec, alpha=0.15, color=COLORES_BESS['carga'], label='_nolegend_')
    ax.fill_between(horas, bess_ent, 0, alpha=0.15, color=COLORES_BESS['danger'], label='_nolegend_')
    
    # Líneas principales - más gruesas y con marcadores
    line_width = 2.8
    
    ax.plot(horas, medidor_rec, 
            color=COLORES_BESS['primary'], 
            linewidth=line_width,
            marker='o',
            markersize=4,
            markeredgecolor='white',
            markeredgewidth=1.5,
            label='IUSA Con BESS')
    
    ax.plot(horas, bess_rec, 
            color=COLORES_BESS['carga'], 
            linewidth=line_width,
            marker='s',
            markersize=4,
            markeredgecolor='white',
            markeredgewidth=1.5,
            label='Carga BESS')
    
    ax.plot(horas, bess_ent, 
            color=COLORES_BESS['danger'], 
            linewidth=line_width,
            marker='^',
            markersize=5,
            markeredgecolor='white',
            markeredgewidth=1.5,
            label='Descarga BESS')
    
    # Configurar ejes
    ax.xaxis.set_major_formatter(mdates.DateFormatter('%H:%M'))
    ax.xaxis.set_major_locator(mdates.HourLocator(interval=2))
    ax.xaxis.set_minor_locator(mdates.HourLocator(interval=1))
    
    # Estilo profesional
    aplicar_estilo_ax(
        ax,
        titulo=f'Perfil de Carga - {fecha_seleccionada}',
        xlabel='Hora del día',
        ylabel='Potencia (kW)'
    )
    
    # Línea base
    ax.axhline(y=0, color='#95a5a6', linestyle='-', linewidth=0.8, alpha=0.5)
    
    # Leyenda mejorada
    ax.legend(
        loc='upper right',
        frameon=True,
        facecolor='#ffffff',
        edgecolor='#e2e8f0',
        fontsize=11,
        borderpad=1,
        handlelength=3,
        shadow=True
    )
    
    plt.xticks(rotation=45, ha='right')
    plt.tight_layout()
    
    return fig

def graficar_arbitraje_periodos(arbitraje_data, fecha_seleccionada):
    """Gráfica de barras para arbitraje por periodo"""
    
    fig, ax = plt.subplots(figsize=(10, 5.5), facecolor='#f8f9fa')
    ax.set_facecolor('#ffffff')
    
    # Preparar datos
    periodos = ['Base', 'Intermedio', 'Punta']
    valores = [arbitraje_data['arbitraje'].get(p, 0) for p in periodos]
    colores = [colores_periodo(p) for p in periodos]
    
    # Barras con estilo
    bars = ax.bar(
        periodos, 
        valores, 
        color=colores,
        edgecolor='white',
        linewidth=2,
        width=0.6,
        alpha=0.85,
        zorder=3
    )
    
    # Añadir valores encima de las barras
    for bar, valor in zip(bars, valores):
        height = bar.get_height()
        color_texto = '#1a202c' if abs(valor) > 0 else '#95a5a6'
        offset = 15 if valor >= 0 else -15
        
        ax.text(
            bar.get_x() + bar.get_width()/2., 
            height + (1 if valor >= 0 else -1) * 1.5,
            f'${valor:,.0f}',
            ha='center', 
            va='bottom' if valor >= 0 else 'top',
            fontsize=12, 
            fontweight='bold',
            color=color_texto
        )
    
    # Línea base
    ax.axhline(y=0, color='#4a5568', linestyle='-', linewidth=1.5, alpha=0.3, zorder=1)
    
    # Estilo profesional
    aplicar_estilo_ax(
        ax,
        titulo=f'💹 Arbitraje por Periodo - {fecha_seleccionada}',
        xlabel='Periodo',
        ylabel='Arbitraje ($)'
    )
    
    # Grid solo en Y
    ax.grid(True, axis='y', linestyle='--', alpha=0.4, color='#e8ecef', zorder=0)
    ax.grid(False, axis='x')
    
    # Ajustar límites
    max_val = max(abs(v) for v in valores) if valores else 1
    padding = max_val * 0.15
    ax.set_ylim(min(valores) - padding if min(valores) < 0 else 0 - padding, 
                max(valores) + padding if max(valores) > 0 else 1)
    
    plt.tight_layout()
    return fig

def graficar_consumo_diario(df_dia, prefijo, fecha_seleccionada):
    """Gráfica de consumo diario por periodo"""
    
    # Agrupar por periodo
    if 'PERIODO' not in df_dia.columns:
        fig, ax = plt.subplots(figsize=(12, 5), facecolor='#f8f9fa')
        ax.text(0.5, 0.5, 'Datos no disponibles', transform=ax.transAxes,
                ha='center', va='center', fontsize=14, color='#95a5a6')
        ax.set_facecolor('#ffffff')
        plt.close()
        return fig
    
    consumo = df_dia.groupby('PERIODO').agg({
        'KWH_REC_BESS': 'sum',
        'KWH_ENT_BESS': 'sum'
    }).reset_index()
    
    fig, ax = plt.subplots(figsize=(10, 5), facecolor='#f8f9fa')
    ax.set_facecolor('#ffffff')
    
    # Configurar barras agrupadas
    periodos = ['Base', 'Intermedio', 'Punta']
    x = np.arange(len(periodos))
    width = 0.35
    
    carga = [consumo[consumo['PERIODO'] == p]['KWH_REC_BESS'].sum() for p in periodos]
    descarga = [consumo[consumo['PERIODO'] == p]['KWH_ENT_BESS'].sum() for p in periodos]
    
    bars1 = ax.bar(x - width/2, carga, width, 
                   label='Carga BESS', 
                   color=COLORES_BESS['carga'],
                   edgecolor='white',
                   linewidth=1.5,
                   alpha=0.85)
    
    bars2 = ax.bar(x + width/2, descarga, width, 
                   label='Descarga BESS',
                   color=COLORES_BESS['danger'],
                   edgecolor='white',
                   linewidth=1.5,
                   alpha=0.85)
    
    # Añadir valores
    for bar in bars1:
        height = bar.get_height()
        if height > 0:
            ax.text(bar.get_x() + bar.get_width()/2., height + 2,
                   f'{height:.0f}', ha='center', va='bottom', fontsize=10, fontweight='bold')
    
    for bar in bars2:
        height = bar.get_height()
        if height > 0:
            ax.text(bar.get_x() + bar.get_width()/2., height + 2,
                   f'{height:.0f}', ha='center', va='bottom', fontsize=10, fontweight='bold')
    
    ax.set_xticks(x)
    ax.set_xticklabels(periodos)
    
    # Estilo profesional
    aplicar_estilo_ax(
        ax,
        titulo=f'⚡ Carga vs Descarga BESS por Periodo - {fecha_seleccionada}',
        xlabel='Periodo',
        ylabel='Energía (kWh)'
    )
    
    ax.grid(True, axis='y', linestyle='--', alpha=0.4, color='#e8ecef')
    ax.grid(False, axis='x')
    
    ax.legend(
        frameon=True,
        facecolor='#ffffff',
        edgecolor='#e2e8f0',
        fontsize=11,
        loc='upper right'
    )
    
    plt.tight_layout()
    return fig

def graficar_tendencia_mensual(prefijo):
    """Gráfica de tendencia mensual de consumo"""
    
    ruta_dia = os.path.join(DIRECTORIO_REPORTES, f'ENERGIA_{prefijo}_POR_DIA.csv')
    if not os.path.exists(ruta_dia):
        fig, ax = plt.subplots(figsize=(12, 5), facecolor='#f8f9fa')
        ax.text(0.5, 0.5, 'Datos no disponibles', transform=ax.transAxes,
                ha='center', va='center', fontsize=14, color='#95a5a6')
        ax.set_facecolor('#ffffff')
        plt.close()
        return fig
    
    df_dia = pd.read_csv(ruta_dia)
    df_dia['FECHA_DT'] = pd.to_datetime(df_dia['FECHA'], format='%d/%m/%Y')
    df_dia = df_dia.sort_values('FECHA_DT')
    
    # Calcular consumo total diario
    df_dia['CONSUMO_TOTAL'] = df_dia['BASE_REC'] + df_dia['INTERMEDIO_REC'] + df_dia['PUNTA_REC']
    
    fig, ax = plt.subplots(figsize=(14, 5.5), facecolor='#f8f9fa')
    ax.set_facecolor('#ffffff')
    
    # Línea de tendencia
    ax.plot(df_dia['FECHA_DT'], df_dia['CONSUMO_TOTAL'],
            color=COLORES_BESS['primary'],
            linewidth=3,
            marker='o',
            markersize=6,
            markeredgecolor='white',
            markeredgewidth=1.5,
            label='Consumo Total')
    
    # Área sombreada debajo de la línea
    ax.fill_between(df_dia['FECHA_DT'], 0, df_dia['CONSUMO_TOTAL'],
                    alpha=0.15, color=COLORES_BESS['primary'])
    
    # Línea de tendencia (promedio móvil)
    if len(df_dia) > 7:
        media_movil = df_dia['CONSUMO_TOTAL'].rolling(window=7, min_periods=3).mean()
        ax.plot(df_dia['FECHA_DT'], media_movil,
                color=COLORES_BESS['accent'],
                linewidth=2.5,
                linestyle='--',
                alpha=0.7,
                label='Tendencia (7 días)')
    
    # Estilo profesional
    aplicar_estilo_ax(
        ax,
        titulo=f'📈 Tendencia de Consumo Diario - {prefijo}',
        xlabel='Fecha',
        ylabel='Energía (kWh)'
    )
    
    ax.xaxis.set_major_formatter(mdates.DateFormatter('%d/%m'))
    ax.xaxis.set_major_locator(mdates.DayLocator(interval=3))
    
    ax.legend(
        frameon=True,
        facecolor='#ffffff',
        edgecolor='#e2e8f0',
        fontsize=11,
        loc='upper left'
    )
    
    plt.xticks(rotation=45, ha='right')
    plt.tight_layout()
    return fig

def calcular_arbitraje_diario(df_dia, tarifas, mes):
    """Calcula el arbitraje diario detallado"""
    df_periodo = df_dia.groupby('PERIODO').agg({
        'BESS_REC_kW': 'mean',
        'BESS_ENT_kW': 'mean',
        'KWH_REC_BESS': 'sum',
        'KWH_ENT_BESS': 'sum',
    }).reset_index()
    
    energia = {}
    for _, row in df_periodo.iterrows():
        periodo = row['PERIODO']
        energia[periodo] = {
            'carga_kwh': row['KWH_REC_BESS'],
            'descarga_kwh': row['KWH_ENT_BESS'],
            'precio': tarifas.get(periodo, {}).get(mes, 0)
        }
    
    arbitraje = {}
    total_arbitraje = 0
    total_carga = 0
    total_descarga = 0
    
    for periodo in ['Base', 'Intermedio', 'Punta']:
        if periodo in energia:
            carga = energia[periodo]['carga_kwh']
            descarga = energia[periodo]['descarga_kwh']
            precio = energia[periodo]['precio']
            arbitraje[periodo] = (descarga - carga) * precio
            total_arbitraje += arbitraje[periodo]
            total_carga += carga
            total_descarga += descarga
    
    return {
        'arbitraje': arbitraje,
        'total_arbitraje': total_arbitraje,
        'total_carga': total_carga,
        'total_descarga': total_descarga,
        'eficiencia': (total_descarga / total_carga * 100) if total_carga > 0 else 0
    }

def mostrar_metrica_arbitraje(valor, periodo=None):
    """Muestra una métrica de arbitraje con colores"""
    if valor >= 0:
        color = '#27ae60'
        icono = '📈'
        bg_color = '#f0fff4'
        border_color = '#27ae60'
    else:
        color = '#e74c3c'
        icono = '📉'
        bg_color = '#fff5f5'
        border_color = '#e74c3c'
    
    if periodo:
        return f"""
        <div style="background-color: {bg_color}; border-radius: 12px; padding: 15px; text-align: center; border-left: 6px solid {border_color}; box-shadow: 0 2px 8px rgba(0,0,0,0.08);">
            <div style="color: #4a5568; font-size: 13px; font-weight: 600;">{periodo}</div>
            <div style="color: {color}; font-size: 22px; font-weight: bold; margin-top: 4px;">{icono} ${valor:,.0f}</div>
        </div>
        """
    else:
        return f"""
        <div style="background: linear-gradient(135deg, #1a202c 0%, #2d3748 100%); border-radius: 16px; padding: 20px; text-align: center; border: 2px solid {color}; box-shadow: 0 4px 12px rgba(0,0,0,0.15);">
            <div style="color: #e2e8f0; font-size: 14px; font-weight: 600; letter-spacing: 1px;">💹 ARBITRAJE TOTAL</div>
            <div style="color: {color}; font-size: 36px; font-weight: bold; margin-top: 4px;">{icono} ${valor:,.0f}</div>
        </div>
        """

def mostrar_tarjeta_bess(carga, descarga, eficiencia):
    """Muestra tarjeta de resumen BESS"""
    col1, col2, col3 = st.columns(3)
    with col1:
        st.metric(
            label="⚡ Carga BESS", 
            value=f"{carga:,.0f} kWh",
            delta=None,
            help="Energía consumida por el BESS"
        )
    with col2:
        st.metric(
            label="🔋 Descarga BESS", 
            value=f"{descarga:,.0f} kWh",
            delta=None,
            help="Energía entregada por el BESS"
        )
    with col3:
        color = "normal"
        if eficiencia >= 80:
            color = "off"
        elif eficiencia >= 60:
            color = "inverse"
        else:
            color = "off"
        st.metric(
            label="📊 Eficiencia", 
            value=f"{eficiencia:.1f}%",
            delta=f"{eficiencia - 85:.1f}%",
            delta_color="normal" if eficiencia >= 80 else "inverse",
            help="Eficiencia = (Descarga / Carga) × 100"
        )

# ========== FUNCIONES DE PROCESAMIENTO (del código original) ==========

def procesar_archivo_verificacion(ruta_origen, ruta_destino, nombre_archivo):
    ruta_completa_origen = os.path.join(ruta_origen, nombre_archivo)
    ruta_completa_destino = os.path.join(ruta_destino, nombre_archivo)
    if not os.path.exists(ruta_completa_origen):
        return False, f"No se encuentra {nombre_archivo}"
    try:
        perfil = pd.read_csv(ruta_completa_origen, encoding='utf-8-sig')
        registros_originales = len(perfil)
        perfil_sin_duplicados = perfil.drop_duplicates(subset=['Fecha'], keep='first')
        renglones_duplicados = len(perfil) - len(perfil_sin_duplicados)
        perfil_sin_duplicados['Fecha'] = pd.to_datetime(perfil_sin_duplicados['Fecha'])
        perfil_sin_duplicados = perfil_sin_duplicados.sort_values(by='Fecha', ascending=True).reset_index(drop=True)
        num_registros = len(perfil_sin_duplicados)
        fi = perfil_sin_duplicados.iloc[0, 0]
        ff = perfil_sin_duplicados.iloc[num_registros - 1, 0]
        dias = (ff - fi).days + 1
        registros_esperados = dias * 288
        Fecha_Correcta = fi
        x = 0
        Faltantes = 0
        Perfiles_faltantes = None
        primera_vez = 0
        Frecuencia_Perfil_MIN = 5
        columnas = perfil.columns.tolist()
        while x < num_registros:
            fecha_archivo = perfil_sin_duplicados.iloc[x, 0]
            if fecha_archivo != Fecha_Correcta:
                nuevo_registro = {'Fecha': Fecha_Correcta}
                for col in columnas[1:]:
                    nuevo_registro[col] = 0
                if primera_vez == 0:
                    Perfiles_faltantes = pd.DataFrame([nuevo_registro])
                    primera_vez = 1
                else:
                    Perfiles_faltantes = pd.concat([Perfiles_faltantes, pd.DataFrame([nuevo_registro])], ignore_index=True)
                x = x - 1
                Faltantes = Faltantes + 1
            x = x + 1
            Fecha_Correcta = Fecha_Correcta + timedelta(minutes=Frecuencia_Perfil_MIN)
        if Faltantes != 0:
            perfil_completo = pd.concat([perfil_sin_duplicados, Perfiles_faltantes], ignore_index=True)
        else:
            perfil_completo = perfil_sin_duplicados
        perfil_completo['Fecha'] = pd.to_datetime(perfil_completo['Fecha'])
        perfil_completo = perfil_completo.sort_values(by='Fecha', ascending=True).reset_index(drop=True)
        os.makedirs(ruta_destino, exist_ok=True)
        perfil_completo.to_csv(ruta_completa_destino, index=False)
        return True, {
            'archivo': nombre_archivo,
            'registros_originales': registros_originales,
            'duplicados_eliminados': renglones_duplicados,
            'faltantes_insertados': Faltantes,
            'registros_finales': len(perfil_completo),
            'fecha_inicial': fi.strftime('%Y-%m-%d %H:%M'),
            'fecha_final': ff.strftime('%Y-%m-%d %H:%M')
        }
    except Exception as e:
        return False, str(e)

def verificar_datos_fuente():
    archivos = ['Banco1.csv', 'BESS.csv', 'ION.csv']
    resultados = {}
    for archivo in archivos:
        ruta_origen = os.path.join(DIRECTORIO_FUENTE, archivo)
        if os.path.exists(ruta_origen):
            exito, info = procesar_archivo_verificacion(DIRECTORIO_FUENTE, DIRECTORIO_PROCESADOS, archivo)
            if exito:
                resultados[archivo] = info
            else:
                resultados[archivo] = {'error': info}
        else:
            resultados[archivo] = {'error': f'Archivo no encontrado: {archivo}'}
    return resultados

# ========== INTERFAZ STREAMLIT ==========

def main():
    st.title("⚡ BESS - Sistema de Procesamiento y Reportes de Energía")
    st.markdown("### Sistema de Análisis de BESS vs ION/BANCO1")
    st.markdown("---")
    
    # Sidebar
    with st.sidebar:
        st.header("📋 Control")
        st.markdown("---")
        
        # Sección de verificación
        st.subheader("1. Verificar Datos")
        if st.button("🔍 Verificar y Limpiar", use_container_width=True):
            with st.spinner("Verificando archivos..."):
                resultados = verificar_datos_fuente()
                st.session_state['verificacion'] = resultados
            st.success("✅ Verificación completada")
            st.rerun()
        
        # Sección de reporte
        st.subheader("2. Generar Reporte")
        medidor = st.selectbox("Seleccionar Medidor", ["ION", "BANCO"], key="medidor_select")
        
        if st.button("🚀 Procesar Reportes BESS", use_container_width=True):
            with st.spinner("Generando reportes..."):
                from bess_core import reporte_bess
                exito, msg_ion, msg_banco = reporte_bess()
                if exito:
                    st.success("✅ Reportes generados exitosamente")
                else:
                    st.warning(f"⚠️ Procesamiento parcial")
            st.rerun()
        
        st.markdown("---")
        
        # Sección de tarifas
        st.subheader("3. Tarifas")
        tarifas = cargar_tarifas()
        mes_actual = datetime.now().month
        if tarifas:
            col1, col2, col3 = st.columns(3)
            with col1:
                st.metric("Base", f"${tarifas['Base'].get(mes_actual, 0):.4f}")
            with col2:
                st.metric("Intermedio", f"${tarifas['Intermedio'].get(mes_actual, 0):.4f}")
            with col3:
                st.metric("Punta", f"${tarifas['Punta'].get(mes_actual, 0):.4f}")
        
        st.markdown("---")
        st.caption("Sistema BESS v4.0")
    
    # Área principal
    tab1, tab2, tab3, tab4 = st.tabs(["📊 Dashboard", "💹 Análisis de Arbitraje", "📄 Reporte PDF", "📁 Archivos"])
    
    with tab1:
        st.header("📊 Dashboard de Energía")
        
        # Verificar si hay datos
        ruta_ion = os.path.join(DIRECTORIO_REPORTES, 'COMBINADO_POR_MINUTO_ION.csv')
        ruta_banco = os.path.join(DIRECTORIO_REPORTES, 'COMBINADO_POR_MINUTO_BANCO.csv')
        
        if not os.path.exists(ruta_ion) and not os.path.exists(ruta_banco):
            st.warning("⚠️ No hay datos procesados. Ejecuta 'Procesar Reportes BESS' primero.")
        else:
            medidor_dash = st.selectbox("Medidor para Dashboard", ["ION", "BANCO"], key="dash_medidor")
            prefijo = 'ION' if medidor_dash == 'ION' else 'BANCO'
            ruta_datos = os.path.join(DIRECTORIO_REPORTES, f'COMBINADO_POR_MINUTO_{prefijo}.csv')
            
            if os.path.exists(ruta_datos):
                df_dash = pd.read_csv(ruta_datos)
                df_dash['DATETIME'] = pd.to_datetime(df_dash['FECHA_HORA'], format='%d/%m/%Y %H:%M')
                
                fechas_disponibles = sorted(df_dash['DATETIME'].dt.date.unique())
                fechas_str = [d.strftime('%d/%m/%Y') for d in fechas_disponibles]
                
                col_fecha, col_vacio = st.columns([2, 1])
                with col_fecha:
                    fecha_seleccionada = st.selectbox("Seleccionar Fecha", fechas_str, key="dash_fecha")
                
                if fecha_seleccionada:
                    fecha_dt = datetime.strptime(fecha_seleccionada, '%d/%m/%Y')
                    inicio = fecha_dt.replace(hour=0, minute=0, second=0)
                    fin = (fecha_dt + timedelta(days=1)).replace(hour=0, minute=0, second=0)
                    
                    mask = (df_dash['DATETIME'] >= inicio) & (df_dash['DATETIME'] < fin)
                    df_dia = df_dash[mask].copy()
                    df_dia = df_dia.sort_values('DATETIME').reset_index(drop=True)
                    
                    if not df_dia.empty:
                        # === SECCIÓN DE ARBITRAJE (Panel superior) ===
                        st.subheader("💹 Arbitraje de Energía")
                        
                        tarifas = cargar_tarifas()
                        mes = fecha_dt.month
                        arbitraje_data = calcular_arbitraje_diario(df_dia, tarifas, mes)
                        
                        # Mostrar tarjetas de arbitraje por periodo
                        col1, col2, col3, col4 = st.columns(4)
                        
                        with col1:
                            st.markdown(mostrar_metrica_arbitraje(
                                arbitraje_data['arbitraje'].get('Base', 0), 
                                "Base"
                            ), unsafe_allow_html=True)
                        
                        with col2:
                            st.markdown(mostrar_metrica_arbitraje(
                                arbitraje_data['arbitraje'].get('Intermedio', 0), 
                                "Intermedio"
                            ), unsafe_allow_html=True)
                        
                        with col3:
                            st.markdown(mostrar_metrica_arbitraje(
                                arbitraje_data['arbitraje'].get('Punta', 0), 
                                "Punta"
                            ), unsafe_allow_html=True)
                        
                        with col4:
                            st.markdown(mostrar_metrica_arbitraje(
                                arbitraje_data['total_arbitraje'], 
                                None
                            ), unsafe_allow_html=True)
                        
                        # Métricas BESS
                        st.markdown("---")
                        mostrar_tarjeta_bess(
                            arbitraje_data['total_carga'],
                            arbitraje_data['total_descarga'],
                            arbitraje_data['eficiencia']
                        )
                        
                        st.markdown("---")
                        
                        # Gráfica 1: Comparación IUSA
                        st.subheader("📊 Comparación IUSA")
                        fig1 = graficar_comparacion_iusa(df_dia, prefijo, fecha_seleccionada)
                        st.pyplot(fig1)
                        plt.close(fig1)
                        
                        # Gráfica 2: Perfil de Carga
                        st.subheader("⚡ Perfil de Carga")
                        fig2 = graficar_perfil_carga(df_dia, prefijo, fecha_seleccionada)
                        st.pyplot(fig2)
                        plt.close(fig2)
                        
                        # Gráfica 3: Carga vs Descarga por Periodo
                        st.subheader("⚡ Carga vs Descarga BESS")
                        fig3 = graficar_consumo_diario(df_dia, prefijo, fecha_seleccionada)
                        st.pyplot(fig3)
                        plt.close(fig3)
                        
                        # Gráfica 4: Tendencia mensual
                        st.subheader("📈 Tendencia de Consumo")
                        fig4 = graficar_tendencia_mensual(prefijo)
                        st.pyplot(fig4)
                        plt.close(fig4)
                        
                    else:
                        st.warning(f"No hay datos para la fecha {fecha_seleccionada}")
            else:
                st.warning(f"No se encontraron datos para {medidor_dash}")
    
    with tab2:
        st.header("💹 Análisis Detallado de Arbitraje")
        
        ruta_ion = os.path.join(DIRECTORIO_REPORTES, 'COMBINADO_POR_MINUTO_ION.csv')
        ruta_banco = os.path.join(DIRECTORIO_REPORTES, 'COMBINADO_POR_MINUTO_BANCO.csv')
        
        if not os.path.exists(ruta_ion) and not os.path.exists(ruta_banco):
            st.warning("⚠️ No hay datos procesados. Ejecuta 'Procesar Reportes BESS' primero.")
        else:
            medidor_arb = st.selectbox("Medidor para Análisis", ["ION", "BANCO"], key="arb_medidor")
            prefijo_arb = 'ION' if medidor_arb == 'ION' else 'BANCO'
            ruta_datos_arb = os.path.join(DIRECTORIO_REPORTES, f'COMBINADO_POR_MINUTO_{prefijo_arb}.csv')
            
            if os.path.exists(ruta_datos_arb):
                df_arb = pd.read_csv(ruta_datos_arb)
                df_arb['DATETIME'] = pd.to_datetime(df_arb['FECHA_HORA'], format='%d/%m/%Y %H:%M')
                
                fechas_arb = sorted(df_arb['DATETIME'].dt.date.unique())
                fechas_arb_str = [d.strftime('%d/%m/%Y') for d in fechas_arb]
                
                fecha_arb = st.selectbox("Seleccionar Fecha", fechas_arb_str, key="arb_fecha")
                
                if fecha_arb:
                    fecha_dt_arb = datetime.strptime(fecha_arb, '%d/%m/%Y')
                    inicio_arb = fecha_dt_arb.replace(hour=0, minute=0, second=0)
                    fin_arb = (fecha_dt_arb + timedelta(days=1)).replace(hour=0, minute=0, second=0)
                    
                    mask_arb = (df_arb['DATETIME'] >= inicio_arb) & (df_arb['DATETIME'] < fin_arb)
                    df_dia_arb = df_arb[mask_arb].copy()
                    df_dia_arb = df_dia_arb.sort_values('DATETIME').reset_index(drop=True)
                    
                    if not df_dia_arb.empty:
                        tarifas = cargar_tarifas()
                        mes_arb = fecha_dt_arb.month
                        arbitraje_data_arb = calcular_arbitraje_diario(df_dia_arb, tarifas, mes_arb)
                        
                        # Tabla detallada de arbitraje
                        st.subheader("📊 Detalle de Arbitraje por Periodo")
                        
                        data_arb = []
                        for periodo in ['Base', 'Intermedio', 'Punta']:
                            carga = df_dia_arb[df_dia_arb['PERIODO'] == periodo]['KWH_REC_BESS'].sum()
                            descarga = df_dia_arb[df_dia_arb['PERIODO'] == periodo]['KWH_ENT_BESS'].sum()
                            precio = tarifas.get(periodo, {}).get(mes_arb, 0)
                            arbitraje = (descarga - carga) * precio
                            
                            data_arb.append({
                                'Periodo': periodo,
                                'Carga (kWh)': f"{carga:,.2f}",
                                'Descarga (kWh)': f"{descarga:,.2f}",
                                'Precio ($/kWh)': f"${precio:.4f}",
                                'Arbitraje ($)': f"${arbitraje:,.0f}"
                            })
                        
                        total_carga = df_dia_arb['KWH_REC_BESS'].sum()
                        total_descarga = df_dia_arb['KWH_ENT_BESS'].sum()
                        total_arbitraje = arbitraje_data_arb['total_arbitraje']
                        
                        data_arb.append({
                            'Periodo': '**TOTAL**',
                            'Carga (kWh)': f"**{total_carga:,.2f}**",
                            'Descarga (kWh)': f"**{total_descarga:,.2f}**",
                            'Precio ($/kWh)': '—',
                            'Arbitraje ($)': f"**${total_arbitraje:,.0f}**"
                        })
                        
                        df_arb_tabla = pd.DataFrame(data_arb)
                        st.dataframe(df_arb_tabla, use_container_width=True, hide_index=True)
                        
                        # Gráfica de arbitraje por periodo
                        st.subheader("📊 Comparativa de Arbitraje por Periodo")
                        fig_arb = graficar_arbitraje_periodos(arbitraje_data_arb, fecha_arb)
                        st.pyplot(fig_arb)
                        plt.close(fig_arb)
                        
                        # Análisis de eficiencia
                        st.subheader("📈 Análisis de Eficiencia BESS")
                        col1, col2, col3 = st.columns(3)
                        
                        with col1:
                            st.metric(
                                "⚡ Energía de Carga", 
                                f"{total_carga:,.2f} kWh",
                                help="Energía consumida por el BESS para cargarse"
                            )
                        with col2:
                            st.metric(
                                "🔋 Energía de Descarga", 
                                f"{total_descarga:,.2f} kWh",
                                help="Energía entregada por el BESS"
                            )
                        with col3:
                            eficiencia = (total_descarga / total_carga * 100) if total_carga > 0 else 0
                            st.metric(
                                "📊 Eficiencia", 
                                f"{eficiencia:.1f}%",
                                delta=f"{eficiencia - 85:.1f}%" if eficiencia > 0 else None,
                                help="Relación entre energía descargada y cargada"
                            )
                    else:
                        st.warning(f"No hay datos para la fecha {fecha_arb}")
            else:
                st.warning(f"No se encontraron datos para {medidor_arb}")

if __name__ == "__main__":
    main()