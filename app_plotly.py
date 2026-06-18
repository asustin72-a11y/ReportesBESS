"""
BESS - Sistema de Procesamiento y Reportes - Web App
Versión con gráficas Plotly interactivas y layout mejorado
"""

import streamlit as st
import pandas as pd
import numpy as np
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

# Importar estilos y funciones
from styles import (
    COLORES_BESS,
    colores_periodo,
    graficar_comparacion_iusa_plotly,
    graficar_perfil_carga_plotly,
    graficar_arbitraje_periodos_plotly,
    graficar_consumo_diario_plotly,
    graficar_tendencia_mensual_plotly,
    graficar_dispersion_plotly,
    graficar_sankey_plotly,
    aplicar_estilo_plotly
)

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
            help="Energía consumida por el BESS"
        )
    with col2:
        st.metric(
            label="🔋 Descarga BESS", 
            value=f"{descarga:,.0f} kWh",
            help="Energía entregada por el BESS"
        )
    with col3:
        st.metric(
            label="📊 Eficiencia", 
            value=f"{eficiencia:.1f}%",
            delta=f"{eficiencia - 85:.1f}%",
            delta_color="normal" if eficiencia >= 80 else "inverse",
            help="Eficiencia = (Descarga / Carga) × 100"
        )

# ========== FUNCIONES DE PROCESAMIENTO ==========

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

# ========== FUNCIONES PARA REPORTE PDF ==========

def get_mes_espanol(mes_numero):
    meses = {1: 'Enero', 2: 'Febrero', 3: 'Marzo', 4: 'Abril', 5: 'Mayo', 6: 'Junio',
             7: 'Julio', 8: 'Agosto', 9: 'Septiembre', 10: 'Octubre', 11: 'Noviembre', 12: 'Diciembre'}
    return meses.get(mes_numero, '')

def formatear_fecha_espanol(fecha_dt):
    dia = fecha_dt.day
    mes = get_mes_espanol(fecha_dt.month)
    ano = fecha_dt.year
    return f"{dia} de {mes} de {ano}"

def buscar_logo():
    posibles_rutas = [
        os.path.join(DIRECTORIO_BASE, 'LogoIUSASOL.jpeg'),
        os.path.join(DIRECTORIO_TARIFAS, 'LogoIUSASOL.jpeg'),
        os.path.join(DIRECTORIO_REPORTES_DIARIOS, 'LogoIUSASOL.jpeg'),
        'LogoIUSASOL.jpeg'
    ]
    for ruta in posibles_rutas:
        if os.path.exists(ruta):
            return ruta
    return None

def generar_reporte_pdf(fecha_str, medidor):
    """Genera el reporte PDF utilizando reportlab"""
    try:
        from reportlab.lib.pagesizes import letter, landscape
        from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Image, Table, TableStyle
        from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
        from reportlab.lib.units import inch
        from reportlab.lib import colors
        from reportlab.lib.enums import TA_CENTER, TA_RIGHT, TA_LEFT
        from PIL import Image as PILImage
        import matplotlib.pyplot as plt
        import matplotlib.dates as mdates
        
        prefijo = 'ION' if medidor == 'ION' else 'BANCO'
        
        # Cargar datos
        ruta_combinado = os.path.join(DIRECTORIO_REPORTES, f'COMBINADO_POR_MINUTO_{prefijo}.csv')
        ruta_acumulados = os.path.join(DIRECTORIO_REPORTES, f'ACUMULADOS_{prefijo}.csv')
        ruta_bess_dia = os.path.join(DIRECTORIO_REPORTES, 'ENERGIA_BESS_POR_DIA.csv')
        
        if not os.path.exists(ruta_combinado):
            return False, "No se encontraron datos para generar el reporte"
        
        df_combinado = pd.read_csv(ruta_combinado)
        df_combinado['DATETIME'] = pd.to_datetime(df_combinado['FECHA_HORA'], format='%d/%m/%Y %H:%M')
        
        fecha_dt = datetime.strptime(fecha_str, '%d/%m/%Y')
        inicio = fecha_dt.replace(hour=0, minute=0, second=0)
        fin = (fecha_dt + timedelta(days=1)).replace(hour=0, minute=0, second=0)
        
        mask = (df_combinado['DATETIME'] >= inicio) & (df_combinado['DATETIME'] < fin)
        df_dia = df_combinado[mask].copy()
        df_dia = df_dia.sort_values('DATETIME').reset_index(drop=True)
        
        if len(df_dia) == 0:
            return False, f"No hay datos para la fecha {fecha_str}"
        
        # Nombre del archivo
        nombre_archivo = f'Reporte_{medidor}_{fecha_dt.strftime("%Y%m%d")}.pdf'
        ruta_pdf = os.path.join(DIRECTORIO_REPORTES_DIARIOS, nombre_archivo)
        os.makedirs(DIRECTORIO_REPORTES_DIARIOS, exist_ok=True)
        
        # Crear PDF
        doc = SimpleDocTemplate(ruta_pdf, pagesize=landscape(letter),
                               rightMargin=20, leftMargin=20,
                               topMargin=25, bottomMargin=25)
        
        styles = getSampleStyleSheet()
        styles.add(ParagraphStyle(name='CustomSubtitleRight', parent=styles['Normal'],
                                  fontSize=10, alignment=TA_RIGHT, spaceAfter=1,
                                  textColor=colors.HexColor('#34495e')))
        styles.add(ParagraphStyle(name='Footer', parent=styles['Normal'],
                                  fontSize=7, alignment=TA_CENTER, textColor=colors.HexColor('#7f8c8d')))
        
        archivos_temp = []
        story = []
        
        # Logo
        logo_path = buscar_logo()
        if logo_path:
            try:
                img_logo = PILImage.open(logo_path)
                logo_width = 1.8 * inch
                logo_height = logo_width * (img_logo.height / img_logo.width)
                logo_temp = os.path.join(DIRECTORIO_REPORTES_DIARIOS, 'temp_logo.png')
                img_logo.save(logo_temp, 'PNG', quality=95)
                archivos_temp.append(logo_temp)
                story.append(Image(logo_temp, width=logo_width, height=logo_height))
                story.append(Spacer(1, 0.02*inch))
            except Exception as e:
                pass
        
        # Fecha
        fecha_espanol = formatear_fecha_espanol(fecha_dt)
        story.append(Paragraph("Pastejé, Jocotitlán, Estado de México", styles['CustomSubtitleRight']))
        story.append(Paragraph(f"Reporte del {fecha_espanol}", styles['CustomSubtitleRight']))
        story.append(Spacer(1, 0.05*inch))
        
        # Generar gráfica con matplotlib
        fig, ax = plt.subplots(figsize=(14, 4.5), facecolor='white', dpi=150)
        ax.set_facecolor('#f0f2f5')
        
        horas = df_dia['DATETIME'].values
        iusa_con = df_dia[f'IUSA_CON_BESS_{prefijo}_kW'].values
        bess_rec = df_dia['BESS_REC_kW'].values
        bess_ent = -df_dia['BESS_ENT_kW'].values
        
        ax.fill_between(horas, 0, iusa_con, alpha=0.3, color='#0055a4')
        ax.fill_between(horas, 0, bess_rec, alpha=0.3, color='#00a86b')
        ax.fill_between(horas, bess_ent, 0, alpha=0.3, color='#d62828')
        
        ax.plot(horas, iusa_con, color='#0055a4', linewidth=2.5, label='IUSA 1 - Con BESS')
        ax.plot(horas, bess_rec, color='#00a86b', linewidth=2, label='Carga BESS')
        ax.plot(horas, bess_ent, color='#d62828', linewidth=2, label='Descarga BESS')
        
        ax.set_title('Perfil de Carga', fontsize=16, fontweight='bold')
        ax.set_xlabel('Hora', fontsize=13)
        ax.set_ylabel('Potencia (kW)', fontsize=13)
        ax.grid(True, alpha=0.15)
        ax.xaxis.set_major_formatter(mdates.DateFormatter('%H:%M'))
        ax.xaxis.set_major_locator(mdates.HourLocator(interval=2))
        plt.xticks(rotation=45)
        ax.legend(loc='upper center', fontsize=11, ncol=3)
        
        plt.tight_layout()
        buf = io.BytesIO()
        plt.savefig(buf, format='png', dpi=200, bbox_inches='tight', facecolor='white')
        buf.seek(0)
        plt.close(fig)
        
        img_path = os.path.join(DIRECTORIO_REPORTES_DIARIOS, f'temp_perfil_{prefijo}_{fecha_dt.strftime("%Y%m%d")}.png')
        archivos_temp.append(img_path)
        img = PILImage.open(buf)
        img.save(img_path, 'PNG', quality=95, dpi=(200, 200))
        story.append(Image(img_path, width=10.5*inch, height=4.0*inch))
        story.append(Spacer(1, 0.08*inch))
        
        # Tabla de datos
        tarifas = cargar_tarifas()
        mes = fecha_dt.month
        
        # Cargar datos acumulados
        if os.path.exists(ruta_acumulados):
            df_acum = pd.read_csv(ruta_acumulados)
            fila_acum = df_acum[df_acum['FECHA'] == fecha_str]
        else:
            fila_acum = None
        
        if os.path.exists(ruta_bess_dia):
            df_bess_dia = pd.read_csv(ruta_bess_dia)
            fila_bess = df_bess_dia[df_bess_dia['FECHA'] == fecha_str]
        else:
            fila_bess = None
        
        data = [['Periodo', 'Base', 'Intermedio', 'Punta', 'Total']]
        
        if fila_acum is not None and len(fila_acum) > 0:
            fila = fila_acum.iloc[0]
            consumo_base = int(round(fila.get('BASE_REC_ACUM', 0)))
            consumo_intermedio = int(round(fila.get('INTERMEDIO_REC_ACUM', 0)))
            consumo_punta = int(round(fila.get('PUNTA_REC_ACUM', 0)))
            consumo_total = consumo_base + consumo_intermedio + consumo_punta
            
            demanda_base = int(np.ceil(fila.get('BASE_DEM_CON_BESS_MAX', 0)))
            demanda_intermedio = int(np.ceil(fila.get('INTERMEDIO_DEM_CON_BESS_MAX', 0)))
            demanda_punta = int(np.ceil(fila.get('PUNTA_DEM_CON_BESS_MAX', 0)))
        else:
            consumo_base = consumo_intermedio = consumo_punta = consumo_total = 0
            demanda_base = demanda_intermedio = demanda_punta = 0
        
        if fila_bess is not None and len(fila_bess) > 0:
            fila = fila_bess.iloc[0]
            carga_base = int(round(fila.get('BASE_REC', 0)))
            carga_intermedio = int(round(fila.get('INTERMEDIO_REC', 0)))
            carga_punta = int(round(fila.get('PUNTA_REC', 0)))
            carga_total = carga_base + carga_intermedio + carga_punta
            
            descarga_base = int(round(fila.get('BASE_ENT', 0)))
            descarga_intermedio = int(round(fila.get('INTERMEDIO_ENT', 0)))
            descarga_punta = int(round(fila.get('PUNTA_ENT', 0)))
            descarga_total = descarga_base + descarga_intermedio + descarga_punta
        else:
            carga_base = carga_intermedio = carga_punta = carga_total = 0
            descarga_base = descarga_intermedio = descarga_punta = descarga_total = 0
        
        data.append(['Consumo Mensual (kWh)', f'{consumo_base:,}', f'{consumo_intermedio:,}', f'{consumo_punta:,}', f'{consumo_total:,}'])
        data.append(['Demanda Rolada (kW)', f'{demanda_base:,}', f'{demanda_intermedio:,}', f'{demanda_punta:,}', f'{demanda_punta:,}'])
        data.append(['Carga Diaria (kWh)', f'{carga_base:,}', f'{carga_intermedio:,}', f'{carga_punta:,}', f'{carga_total:,}'])
        data.append(['Descarga Diaria (kWh)', f'{descarga_base:,}', f'{descarga_intermedio:,}', f'{descarga_punta:,}', f'{descarga_total:,}'])
        
        precio_base = tarifas['Base'].get(mes, 0)
        precio_intermedio = tarifas['Intermedio'].get(mes, 0)
        precio_punta = tarifas['Punta'].get(mes, 0)
        
        arbitraje_base = (descarga_base * precio_base) - (carga_base * precio_base)
        arbitraje_intermedio = (descarga_intermedio * precio_intermedio) - (carga_intermedio * precio_intermedio)
        arbitraje_punta = (descarga_punta * precio_punta) - (carga_punta * precio_punta)
        arbitraje_total = arbitraje_base + arbitraje_intermedio + arbitraje_punta
        
        data.append(['Arbitraje de Energia (MXN)', f'${arbitraje_base:,.0f}', f'${arbitraje_intermedio:,.0f}', f'${arbitraje_punta:,.0f}', f'${arbitraje_total:,.0f}'])
        
        tabla = Table(data, colWidths=[2.5*inch, 1.3*inch, 1.3*inch, 1.3*inch, 1.3*inch])
        tabla.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#2c3e50')),
            ('TEXTCOLOR', (0, 0), (-1, 0), colors.white),
            ('ALIGN', (0, 0), (-1, 0), 'CENTER'),
            ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
            ('FONTSIZE', (0, 0), (-1, 0), 11),
            ('FONTNAME', (0, 1), (-1, -1), 'Helvetica'),
            ('FONTSIZE', (0, 1), (-1, -1), 10),
            ('ALIGN', (0, 1), (0, -1), 'LEFT'),
            ('ALIGN', (1, 1), (-1, -1), 'RIGHT'),
            ('BOX', (0, 0), (-1, -1), 1.5, colors.black),
            ('GRID', (0, 0), (-1, -1), 0.5, colors.HexColor('#d5d8dc')),
            ('FONTNAME', (4, 1), (4, -1), 'Helvetica-Bold'),
            ('LEFTPADDING', (0, 0), (-1, -1), 6),
            ('RIGHTPADDING', (0, 0), (-1, -1), 6),
            ('BACKGROUND', (0, 1), (-1, 1), colors.HexColor('#f8f9fa')),
            ('BACKGROUND', (0, 3), (-1, 3), colors.HexColor('#f8f9fa')),
            ('BACKGROUND', (0, 5), (-1, 5), colors.HexColor('#e8f4f8')),
            ('FONTNAME', (0, 5), (-1, 5), 'Helvetica-Bold'),
        ]))
        story.append(tabla)
        story.append(Spacer(1, 0.1*inch))
        
        story.append(Paragraph("Carretera Panamericana Mexico Queretaro S/N km. 100, Pesteje, Jocotitlan, Estado de Mexico", styles['Footer']))
        
        doc.build(story)
        
        # Limpiar archivos temporales
        for archivo in archivos_temp:
            if os.path.exists(archivo):
                try:
                    os.remove(archivo)
                except:
                    pass
        
        return True, ruta_pdf
        
    except Exception as e:
        return False, str(e)

# ========== INTERFAZ STREAMLIT ==========

def main():
    # Cabecera mejorada
    st.title("⚡ BESS - Sistema de Procesamiento y Reportes de Energía")
    st.markdown("### 📊 Análisis de BESS vs ION / BANCO1")
    st.markdown("---")
    
    # Sidebar
    with st.sidebar:
        st.header("📋 Control")
        st.markdown("---")
        
        # Sección de verificación y filtrado
        with st.expander("📁 1. Verificar y Filtrar Datos", expanded=True):
            col1, col2 = st.columns(2)
            with col1:
                if st.button("🔍 Verificar y Limpiar", use_container_width=True):
                    with st.spinner("Verificando archivos..."):
                        resultados = verificar_datos_fuente()
                        st.session_state['verificacion'] = resultados
                    st.success("✅ Verificación completada")
                    st.rerun()
            
            with col2:
                if st.button("📊 Filtrar y Combinar", use_container_width=True):
                    with st.spinner("Filtrando datos..."):
                        from bess_core import filtrar_datos
                        exito, msg = filtrar_datos()
                        if exito:
                            st.success(f"✅ {msg}")
                            st.session_state['filtrado'] = True
                        else:
                            st.error(f"❌ {msg}")
                    st.rerun()
            
            # Mostrar resultados de verificación
            if 'verificacion' in st.session_state:
                with st.expander("📊 Resultados de Verificación", expanded=False):
                    for archivo, info in st.session_state['verificacion'].items():
                        if isinstance(info, dict) and 'error' not in info:
                            st.markdown(f"**{archivo}**")
                            st.write(f"- Registros originales: {info.get('registros_originales', 0)}")
                            st.write(f"- Duplicados eliminados: {info.get('duplicados_eliminados', 0)}")
                            st.write(f"- Faltantes insertados: {info.get('faltantes_insertados', 0)}")
                            st.write(f"- Registros finales: {info.get('registros_finales', 0)}")
                        else:
                            st.warning(f"⚠️ {archivo}: {info.get('error', 'Error desconocido')}")
        
        # Sección de reporte
        with st.expander("📊 2. Generar Reporte BESS", expanded=True):
            #st.info("📌 El proceso genera reportes para AMBOS medidores (ION y BANCO1) simultáneamente")
            #st.info("📌 El proceso genera reportes para AMBOS medidores (ION y BANCO1) simultáneamente")
            if st.button("🚀 Procesar Reportes BESS", use_container_width=True):
                with st.spinner("Generando reportes..."):
                    from bess_core import reporte_bess
                    exito, msg_ion, msg_banco = reporte_bess()
                    if exito:
                        st.success("✅ Reportes generados exitosamente")
                        st.success(f"   ✅ ION: {msg_ion}")
                        st.success(f"   ✅ BANCO1: {msg_banco}")
                    else:
                        st.warning(f"⚠️ Procesamiento parcial")
                        st.warning(f"   ION: {msg_ion}")
                        st.warning(f"   BANCO1: {msg_banco}")
                st.rerun()
                
        st.markdown("---")
        
        # Sección de tarifas
        with st.expander("💰 3. Tarifas", expanded=False):
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
        st.caption("Sistema BESS v5.0")
    
    # Área principal - Pestañas
    tab1, tab2, tab3, tab4 = st.tabs([
        "📊 Dashboard", 
        "💹 Análisis de Arbitraje", 
        "📄 Reporte PDF",
        "📈 Análisis Avanzado"
    ])
    
    with tab1:
        # Título de la sección con mejor formato
        st.markdown("## 📊 Dashboard de Energía")
        st.markdown("---")
        
        # Verificar si hay datos
        ruta_ion = os.path.join(DIRECTORIO_REPORTES, 'COMBINADO_POR_MINUTO_ION.csv')
        ruta_banco = os.path.join(DIRECTORIO_REPORTES, 'COMBINADO_POR_MINUTO_BANCO.csv')
        
        if not os.path.exists(ruta_ion) and not os.path.exists(ruta_banco):
            st.warning("⚠️ No hay datos procesados. Ejecuta 'Procesar Reportes BESS' primero.")
        else:
            # Selector de medidor y fecha en la misma fila
            col1, col2 = st.columns([1, 2])
            with col1:
                medidor_dash = st.selectbox("📌 Medidor", ["ION", "BANCO"], key="dash_medidor")
            with col2:
                prefijo = 'ION' if medidor_dash == 'ION' else 'BANCO'
                ruta_datos = os.path.join(DIRECTORIO_REPORTES, f'COMBINADO_POR_MINUTO_{prefijo}.csv')
                
                if os.path.exists(ruta_datos):
                    df_dash = pd.read_csv(ruta_datos)
                    df_dash['DATETIME'] = pd.to_datetime(df_dash['FECHA_HORA'], format='%d/%m/%Y %H:%M')
                    fechas_disponibles = sorted(df_dash['DATETIME'].dt.date.unique())
                    fechas_str = [d.strftime('%d/%m/%Y') for d in fechas_disponibles]
                    fecha_seleccionada = st.selectbox("📅 Fecha", fechas_str, key="dash_fecha")
                else:
                    st.warning(f"No se encontraron datos para {medidor_dash}")
                    fecha_seleccionada = None
            
            if fecha_seleccionada:
                fecha_dt = datetime.strptime(fecha_seleccionada, '%d/%m/%Y')
                inicio = fecha_dt.replace(hour=0, minute=0, second=0)
                fin = (fecha_dt + timedelta(days=1)).replace(hour=0, minute=0, second=0)
                
                mask = (df_dash['DATETIME'] >= inicio) & (df_dash['DATETIME'] < fin)
                df_dia = df_dash[mask].copy()
                df_dia = df_dia.sort_values('DATETIME').reset_index(drop=True)
                
                if not df_dia.empty:
                    # === SECCIÓN DE ARBITRAJE ===
                    st.markdown("### 💹 Arbitraje de Energía")
                    
                    tarifas = cargar_tarifas()
                    mes = fecha_dt.month
                    arbitraje_data = calcular_arbitraje_diario(df_dia, tarifas, mes)
                    
                    # Mostrar tarjetas de arbitraje en 4 columnas
                    col1, col2, col3, col4 = st.columns(4)
                    with col1:
                        st.markdown(mostrar_metrica_arbitraje(
                            arbitraje_data['arbitraje'].get('Base', 0), "Base"
                        ), unsafe_allow_html=True)
                    with col2:
                        st.markdown(mostrar_metrica_arbitraje(
                            arbitraje_data['arbitraje'].get('Intermedio', 0), "Intermedio"
                        ), unsafe_allow_html=True)
                    with col3:
                        st.markdown(mostrar_metrica_arbitraje(
                            arbitraje_data['arbitraje'].get('Punta', 0), "Punta"
                        ), unsafe_allow_html=True)
                    with col4:
                        st.markdown(mostrar_metrica_arbitraje(
                            arbitraje_data['total_arbitraje'], None
                        ), unsafe_allow_html=True)
                    
                    st.markdown("---")
                    
                    # Métricas BESS en 3 columnas
                    st.markdown("### ⚡ Métricas BESS")
                    mostrar_tarjeta_bess(
                        arbitraje_data['total_carga'],
                        arbitraje_data['total_descarga'],
                        arbitraje_data['eficiencia']
                    )
                    
                    st.markdown("---")
                    
                    # === GRÁFICAS ===
                    # Generar un key único basado en el medidor y fecha
                    key_suffix = f"{medidor_dash}_{fecha_seleccionada.replace('/', '_')}"
                    
                    # Gráfica 1: Comparación IUSA (ancho completo)
                    st.markdown("### 📊 Comparación IUSA")
                    fig1 = graficar_comparacion_iusa_plotly(df_dia, prefijo, fecha_seleccionada)
                    st.plotly_chart(fig1, use_container_width=True, config={'displayModeBar': True}, key=f"fig_iusa_{key_suffix}")
                    
                    # Gráfica 2: Perfil de Carga (ancho completo)
                    st.markdown("### ⚡ Perfil de Carga")
                    fig2 = graficar_perfil_carga_plotly(df_dia, prefijo, fecha_seleccionada)
                    st.plotly_chart(fig2, use_container_width=True, config={'displayModeBar': True}, key=f"fig_perfil_{key_suffix}")
                    
                    # Gráfica 3: Carga vs Descarga (ancho completo)
                    st.markdown("### ⚡ Carga vs Descarga BESS")
                    fig3 = graficar_consumo_diario_plotly(df_dia, prefijo, fecha_seleccionada)
                    st.plotly_chart(fig3, use_container_width=True, config={'displayModeBar': True}, key=f"fig_carga_{key_suffix}")
                    
                else:
                    st.warning(f"No hay datos para la fecha {fecha_seleccionada}")
    
    with tab2:
        st.markdown("## 💹 Análisis Detallado de Arbitraje")
        st.markdown("---")
        
        ruta_ion = os.path.join(DIRECTORIO_REPORTES, 'COMBINADO_POR_MINUTO_ION.csv')
        ruta_banco = os.path.join(DIRECTORIO_REPORTES, 'COMBINADO_POR_MINUTO_BANCO.csv')
        
        if not os.path.exists(ruta_ion) and not os.path.exists(ruta_banco):
            st.warning("⚠️ No hay datos procesados. Ejecuta 'Procesar Reportes BESS' primero.")
        else:
            col1, col2 = st.columns([1, 2])
            with col1:
                medidor_arb = st.selectbox("📌 Medidor", ["ION", "BANCO"], key="arb_medidor")
            with col2:
                prefijo_arb = 'ION' if medidor_arb == 'ION' else 'BANCO'
                ruta_datos_arb = os.path.join(DIRECTORIO_REPORTES, f'COMBINADO_POR_MINUTO_{prefijo_arb}.csv')
                
                if os.path.exists(ruta_datos_arb):
                    df_arb = pd.read_csv(ruta_datos_arb)
                    df_arb['DATETIME'] = pd.to_datetime(df_arb['FECHA_HORA'], format='%d/%m/%Y %H:%M')
                    fechas_arb = sorted(df_arb['DATETIME'].dt.date.unique())
                    fechas_arb_str = [d.strftime('%d/%m/%Y') for d in fechas_arb]
                    fecha_arb = st.selectbox("📅 Fecha", fechas_arb_str, key="arb_fecha")
                else:
                    st.warning(f"No se encontraron datos para {medidor_arb}")
                    fecha_arb = None
            
            if fecha_arb:
                key_suffix_arb = f"{medidor_arb}_{fecha_arb.replace('/', '_')}"
                
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
                    st.markdown("### 📊 Detalle de Arbitraje por Periodo")
                    
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
                    st.markdown("### 📊 Comparativa de Arbitraje por Periodo")
                    fig_arb = graficar_arbitraje_periodos_plotly(arbitraje_data_arb, fecha_arb)
                    st.plotly_chart(fig_arb, use_container_width=True, config={'displayModeBar': True}, key=f"fig_arbitraje_{key_suffix_arb}")
                    
                    # Análisis de eficiencia
                    st.markdown("### 📈 Análisis de Eficiencia BESS")
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
    
    with tab3:
        st.markdown("## 📄 Generar Reporte PDF")
        st.markdown("---")
        
        # Verificar si hay datos
        ruta_ion = os.path.join(DIRECTORIO_REPORTES, 'COMBINADO_POR_MINUTO_ION.csv')
        ruta_banco = os.path.join(DIRECTORIO_REPORTES, 'COMBINADO_POR_MINUTO_BANCO.csv')
        
        if not os.path.exists(ruta_ion) and not os.path.exists(ruta_banco):
            st.warning("⚠️ No hay datos procesados. Ejecuta 'Procesar Reportes BESS' primero.")
        else:
            col1, col2 = st.columns([1, 2])
            with col1:
                medidor_pdf = st.selectbox("📌 Medidor", ["ION", "BANCO"], key="pdf_medidor")
            with col2:
                prefijo_pdf = 'ION' if medidor_pdf == 'ION' else 'BANCO'
                ruta_combinado_pdf = os.path.join(DIRECTORIO_REPORTES, f'COMBINADO_POR_MINUTO_{prefijo_pdf}.csv')
                
                if os.path.exists(ruta_combinado_pdf):
                    df_pdf = pd.read_csv(ruta_combinado_pdf)
                    df_pdf['DATETIME'] = pd.to_datetime(df_pdf['FECHA_HORA'], format='%d/%m/%Y %H:%M')
                    fechas_pdf = sorted(df_pdf['DATETIME'].dt.date.unique())
                    fechas_pdf_str = [d.strftime('%d/%m/%Y') for d in fechas_pdf]
                    fecha_pdf = st.selectbox("📅 Fecha", fechas_pdf_str, key="pdf_fecha")
                else:
                    st.warning(f"No se encontraron datos para {medidor_pdf}")
                    fecha_pdf = None
            
            if fecha_pdf:
                st.info(f"📄 Generando reporte para {medidor_pdf} - {fecha_pdf}")
                
                if st.button("📄 Generar Reporte PDF", use_container_width=True, type="primary"):
                    with st.spinner("Generando reporte PDF..."):
                        exito, resultado = generar_reporte_pdf(fecha_pdf, medidor_pdf)
                        
                        if exito:
                            st.success(f"✅ Reporte generado exitosamente")
                            
                            # Mostrar información del archivo
                            st.markdown(f"**📁 Archivo:** `{os.path.basename(resultado)}`")
                            st.markdown(f"**📂 Ubicación:** `{os.path.dirname(resultado)}`")
                            
                            # Botón de descarga
                            with open(resultado, 'rb') as f:
                                pdf_bytes = f.read()
                            
                            st.download_button(
                                label="📥 Descargar PDF",
                                data=pdf_bytes,
                                file_name=os.path.basename(resultado),
                                mime="application/pdf",
                                use_container_width=True
                            )
                        else:
                            st.error(f"❌ Error al generar el reporte: {resultado}")
    
    with tab4:
        st.markdown("## 📈 Análisis Avanzado")
        st.markdown("---")
        
        col1, col2 = st.columns([1, 2])
        with col1:
            medidor_trend = st.selectbox("📌 Medidor", ["ION", "BANCO"], key="trend_medidor")
        with col2:
            prefijo_trend = 'ION' if medidor_trend == 'ION' else 'BANCO'
            st.markdown(f"### 📊 Datos de {medidor_trend}")
        
        # Tendencia mensual
        st.markdown("### 📈 Tendencia de Consumo Diario")
        fig_trend = graficar_tendencia_mensual_plotly(prefijo_trend, DIRECTORIO_REPORTES)
        st.plotly_chart(fig_trend, use_container_width=True, config={'displayModeBar': True}, key=f"fig_trend_{medidor_trend}")
        
        # Estadísticas descriptivas
        st.markdown("### 📊 Estadísticas Descriptivas")
        ruta_dia = os.path.join(DIRECTORIO_REPORTES, f'ENERGIA_{prefijo_trend}_POR_DIA.csv')
        if os.path.exists(ruta_dia):
            df_stats = pd.read_csv(ruta_dia)
            df_stats['FECHA_DT'] = pd.to_datetime(df_stats['FECHA'], format='%d/%m/%Y')
            
            # Calcular estadísticas
            col1, col2, col3, col4 = st.columns(4)
            with col1:
                st.metric("📅 Total Días", len(df_stats))
            with col2:
                st.metric("⚡ Consumo Promedio", f"{df_stats['BASE_REC'].mean() + df_stats['INTERMEDIO_REC'].mean() + df_stats['PUNTA_REC'].mean():,.0f} kWh")
            with col3:
                st.metric("📊 Consumo Máximo", f"{df_stats['BASE_REC'].max() + df_stats['INTERMEDIO_REC'].max() + df_stats['PUNTA_REC'].max():,.0f} kWh")
            with col4:
                st.metric("📉 Consumo Mínimo", f"{df_stats['BASE_REC'].min() + df_stats['INTERMEDIO_REC'].min() + df_stats['PUNTA_REC'].min():,.0f} kWh")
            
            # Mostrar datos
            st.markdown("### 📋 Datos Históricos")
            st.dataframe(df_stats, use_container_width=True)

if __name__ == "__main__":
    main()