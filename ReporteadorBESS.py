"""
BESS - SISTEMA DE PROCESAMIENTO Y REPORTES UNIFICADO
====================================================
Script único que integra:
1. VerificaDatosFuente - Verifica y limpia datos
2. FiltraDatosFuente - Filtra y combina archivos
3. ReporteBESS - Genera reportes de energía
4. GraficaBESS - Dashboard interactivo
5. GeneraReporte - Genera reportes PDF
"""

import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
import matplotlib.dates as mdates
import seaborn as sns
import tkinter as tk
from tkinter import ttk, messagebox
from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg
from datetime import datetime, timedelta
import os
import sys
import shutil
import io
import warnings
from reportlab.lib.pagesizes import letter, landscape
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Image, Table, TableStyle
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import inch
from reportlab.lib import colors
from reportlab.lib.enums import TA_CENTER, TA_RIGHT, TA_LEFT
from PIL import Image as PILImage
warnings.filterwarnings('ignore')

# ========== CONFIGURACIÓN GLOBAL ==========
DIRECTORIO_BASE = 'C:/ReportesBESS'
DIRECTORIO_FUENTE = os.path.join(DIRECTORIO_BASE, 'ArchivosFuente')
DIRECTORIO_PROCESADOS = os.path.join(DIRECTORIO_BASE, 'ArchivosProcesados')
DIRECTORIO_REPORTES = os.path.join(DIRECTORIO_BASE, 'ArchivosReporte')
DIRECTORIO_REPORTES_DIARIOS = os.path.join(DIRECTORIO_BASE, 'ReportesDiarios')
DIRECTORIO_TARIFAS = os.path.join(DIRECTORIO_BASE, 'Tarifas')

# Crear directorios si no existen
for dir_path in [DIRECTORIO_BASE, DIRECTORIO_FUENTE, DIRECTORIO_PROCESADOS, 
                 DIRECTORIO_REPORTES, DIRECTORIO_REPORTES_DIARIOS, DIRECTORIO_TARIFAS]:
    os.makedirs(dir_path, exist_ok=True)

# ========== PARTE 1: VERIFICADOR DE DATOS FUENTE ==========

def crear_barra(progreso, longitud):
    """Crea una barra de progreso para mostrar el avance"""
    barra_llena = int(longitud * (progreso / 100))
    barra = '[' + '#' * barra_llena + ' ' * (longitud - barra_llena) + ']'
    return barra

def procesar_archivo_verificacion(ruta_origen, ruta_destino, nombre_archivo):
    """
    Procesa un archivo CSV verificando duplicados y registros faltantes
    """
    ruta_completa_origen = os.path.join(ruta_origen, nombre_archivo)
    ruta_completa_destino = os.path.join(ruta_destino, nombre_archivo)
    
    if not os.path.exists(ruta_completa_origen):
        print(f"❌ Error: No se encuentra {ruta_completa_origen}")
        return False
    
    print(f"\n{'='*60}")
    print(f"📊 Procesando: {nombre_archivo}")
    print(f"{'='*60}")
    
    try:
        perfil = pd.read_csv(ruta_completa_origen, encoding='utf-8-sig')
        print(f"📁 Archivo original: {nombre_archivo}")
        print(f"📏 Registros originales: {len(perfil)}")
        
        # Eliminar duplicados
        perfil_sin_duplicados = perfil.drop_duplicates(subset=['Fecha'], keep='first')
        renglones_duplicados = len(perfil) - len(perfil_sin_duplicados)
        print(f"🗑️ Renglones duplicados eliminados: {renglones_duplicados}")
        
        perfil_sin_duplicados['Fecha'] = pd.to_datetime(perfil_sin_duplicados['Fecha'])
        perfil_sin_duplicados = perfil_sin_duplicados.sort_values(by='Fecha', ascending=True).reset_index(drop=True)
        
        # Verificar registros faltantes
        num_registros = len(perfil_sin_duplicados)
        fi = perfil_sin_duplicados.iloc[0, 0]
        ff = perfil_sin_duplicados.iloc[num_registros - 1, 0]
        dias = (ff - fi).days + 1
        registros_esperados = dias * 288
        
        print(f"📅 Fecha inicial: {fi.strftime('%Y-%m-%d %H:%M:%S')}")
        print(f"📅 Fecha final: {ff.strftime('%Y-%m-%d %H:%M:%S')}")
        print(f"📊 Registros esperados: {registros_esperados}")
        print(f"📊 Registros actuales: {num_registros}")
        
        # Insertar registros faltantes
        Fecha_Correcta = fi
        x = 0
        Faltantes = 0
        Perfiles_faltantes = None
        primera_vez = 0
        Frecuencia_Perfil_MIN = 5
        columnas = perfil.columns.tolist()
        
        print("\n⏳ Verificando registros faltantes...")
        
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
            
            porcentaje = (x / num_registros) * 100
            barra = crear_barra(porcentaje, 40)
            print(f"{barra} {porcentaje:.1f}%", end='\r')
        
        print("\n✅ Verificación completada")
        print(f"📝 Registros faltantes insertados: {Faltantes}")
        
        if Faltantes != 0:
            perfil_completo = pd.concat([perfil_sin_duplicados, Perfiles_faltantes], ignore_index=True)
        else:
            perfil_completo = perfil_sin_duplicados
        
        perfil_completo['Fecha'] = pd.to_datetime(perfil_completo['Fecha'])
        perfil_completo = perfil_completo.sort_values(by='Fecha', ascending=True).reset_index(drop=True)
        
        os.makedirs(ruta_destino, exist_ok=True)
        ruta_guardado = os.path.join(ruta_destino, nombre_archivo)
        
        if os.path.exists(ruta_guardado):
            backup_path = ruta_guardado.replace('.csv', '_backup.csv')
            shutil.copy2(ruta_guardado, backup_path)
            print(f"💾 Backup creado: {os.path.basename(backup_path)}")
        
        perfil_completo.to_csv(ruta_guardado, index=False)
        print(f"✅ Archivo procesado guardado: {ruta_guardado}")
        print(f"📊 Registros finales: {len(perfil_completo)}")
        
        return True
        
    except Exception as e:
        print(f"❌ Error al procesar {nombre_archivo}: {str(e)}")
        import traceback
        traceback.print_exc()
        return False

def verificar_datos_fuente():
    """Función principal de verificación de datos fuente"""
    archivos = ['Banco1.csv', 'BESS.csv', 'ION.csv']
    
    print("="*70)
    print("🔍 VERIFICADOR DE PERFILES DE CARGA")
    print("="*70)
    print(f"📁 Carpeta origen: {DIRECTORIO_FUENTE}")
    print(f"📁 Carpeta destino: {DIRECTORIO_PROCESADOS}")
    print("="*70)
    
    if not os.path.exists(DIRECTORIO_FUENTE):
        print(f"❌ Error: No existe la carpeta {DIRECTORIO_FUENTE}")
        os.makedirs(DIRECTORIO_FUENTE, exist_ok=True)
        print(f"✅ Carpeta creada: {DIRECTORIO_FUENTE}")
        print("Coloca los archivos (Banco1.csv, BESS.csv, ION.csv) en esta carpeta y ejecuta nuevamente.")
        return False
    
    archivos_encontrados = []
    for archivo in archivos:
        ruta_completa = os.path.join(DIRECTORIO_FUENTE, archivo)
        if os.path.exists(ruta_completa):
            archivos_encontrados.append(archivo)
    
    if not archivos_encontrados:
        print(f"❌ No se encontraron archivos en {DIRECTORIO_FUENTE}")
        return False
    
    print(f"\n📋 Archivos encontrados: {', '.join(archivos_encontrados)}")
    
    resultados = {}
    for archivo in archivos:
        if os.path.exists(os.path.join(DIRECTORIO_FUENTE, archivo)):
            resultados[archivo] = procesar_archivo_verificacion(DIRECTORIO_FUENTE, DIRECTORIO_PROCESADOS, archivo)
        else:
            print(f"\n⚠️ Archivo no encontrado: {archivo} (omitido)")
            resultados[archivo] = False
    
    print("\n" + "="*70)
    print("📊 RESUMEN FINAL VERIFICACIÓN")
    print("="*70)
    for archivo, exito in resultados.items():
        estado = "✅ Éxito" if exito else "❌ Falló"
        print(f"   {archivo}: {estado}")
    
    return all(resultados.values())

# ========== PARTE 2: FILTRADOR DE DATOS ==========

def validar_archivo(ruta):
    """Verifica que el archivo exista"""
    return os.path.exists(ruta)

def leer_archivo_perfil(ruta, nombre_archivo, intercambiar_columnas=False):
    """Lee un archivo de perfil completo"""
    try:
        df = pd.read_csv(ruta, encoding='utf-8-sig')
    except Exception as e:
        print(f"❌ Error al leer {nombre_archivo}: {e}")
        return None
    
    print(f"📁 {nombre_archivo}: {len(df)} registros")
    
    columnas_principales = ['Fecha', 'KWH_REC', 'KWH_ENT']
    for col in columnas_principales:
        if col not in df.columns:
            print(f"⚠️ Advertencia: No se encuentra la columna '{col}' en {nombre_archivo}")
            return None
    
    df['Fecha'] = pd.to_datetime(df['Fecha'], errors='coerce')
    registros_invalidos = df['Fecha'].isna().sum()
    if registros_invalidos > 0:
        print(f"⚠️ {nombre_archivo}: Se eliminaron {registros_invalidos} registros con fecha inválida")
        df = df.dropna(subset=['Fecha'])
    
    df['KWH_REC'] = pd.to_numeric(df['KWH_REC'], errors='coerce').fillna(0)
    df['KWH_ENT'] = pd.to_numeric(df['KWH_ENT'], errors='coerce').fillna(0)
    
    if intercambiar_columnas:
        print(f"🔄 {nombre_archivo}: Intercambiando KWH_REC ↔ KWH_ENT")
        temp_rec = df['KWH_REC'].copy()
        df['KWH_REC'] = df['KWH_ENT']
        df['KWH_ENT'] = temp_rec
    
    print(f"✅ {nombre_archivo}: {len(df)} registros válidos")
    return df

def normalizar_fecha(fecha):
    """Convierte fecha al formato DD/MM/YYYY HH:MM"""
    if isinstance(fecha, str):
        return fecha
    return fecha.strftime('%d/%m/%Y %H:%M')

def generar_archivo_limpio(df, ruta_salida):
    """Genera un archivo CSV limpio"""
    df_limpio = df[['Fecha', 'KWH_REC', 'KWH_ENT']].copy()
    df_limpio['Fecha'] = df_limpio['Fecha'].apply(normalizar_fecha)
    df_limpio.to_csv(ruta_salida, index=False, encoding='utf-8-sig')
    print(f"✅ Archivo generado: {ruta_salida} ({len(df_limpio)} registros)")
    return df_limpio

def filtrar_datos():
    """Función principal de filtrado de datos"""
    print("=" * 70)
    print("📊 PREPROCESADOR DE DATOS")
    print("=" * 70)
    print(f"📁 Carpeta de trabajo: {DIRECTORIO_PROCESADOS}")
    print("=" * 70)
    
    if not os.path.exists(DIRECTORIO_PROCESADOS):
        print(f"❌ Error: No existe la carpeta {DIRECTORIO_PROCESADOS}")
        return False
    
    archivos = {
        'BESS.csv': 'BESS_Filtrado.csv',
        'ION.csv': 'ION_Filtrado.csv',
        'Banco1.csv': 'Banco1_Filtrado.csv'
    }
    
    dfs = {}
    
    for archivo_origen, archivo_destino in archivos.items():
        ruta_origen = os.path.join(DIRECTORIO_PROCESADOS, archivo_origen)
        ruta_destino = os.path.join(DIRECTORIO_PROCESADOS, archivo_destino)
        
        if not validar_archivo(ruta_origen):
            print(f"❌ No se puede continuar sin el archivo {archivo_origen}")
            return False
        
        intercambiar = (archivo_origen == 'Banco1.csv')
        df = leer_archivo_perfil(ruta_origen, archivo_origen, intercambiar)
        if df is None:
            return False
        
        dfs[archivo_origen] = df
    
    # Encontrar fechas comunes
    fechas_bess = set(dfs['BESS.csv']['Fecha'])
    fechas_ion = set(dfs['ION.csv']['Fecha'])
    fechas_banco = set(dfs['Banco1.csv']['Fecha'])
    
    fechas_comunes = fechas_bess.intersection(fechas_ion).intersection(fechas_banco)
    
    print(f"\n📊 Coincidencias (los 3): {len(fechas_comunes)} registros")
    
    if len(fechas_comunes) == 0:
        print("❌ ERROR: No se encontraron fechas coincidentes")
        return False
    
    # Filtrar y guardar
    for archivo_origen, archivo_destino in archivos.items():
        df_filtrado = dfs[archivo_origen][dfs[archivo_origen]['Fecha'].isin(fechas_comunes)].copy()
        df_filtrado = df_filtrado.sort_values('Fecha').reset_index(drop=True)
        ruta_destino = os.path.join(DIRECTORIO_PROCESADOS, archivo_destino)
        generar_archivo_limpio(df_filtrado, ruta_destino)
    
    print("\n" + "=" * 70)
    print("✅ PREPROCESAMIENTO COMPLETADO EXITOSAMENTE")
    print("=" * 70)
    return True

# ========== PARTE 3: REPORTE BESS ==========

def obtener_temporada(fecha):
    """Determina la temporada según la fecha (Región Central)"""
    mes = fecha.month
    dia = fecha.day
    año = fecha.year
    
    primer_domingo_abril = None
    for d in range(1, 8):
        fecha_temp = datetime(año, 4, d)
        if fecha_temp.weekday() == 6:
            primer_domingo_abril = d
            break
    
    ultimo_domingo_octubre = None
    for d in range(31, 24, -1):
        fecha_temp = datetime(año, 10, d)
        if fecha_temp.weekday() == 6:
            ultimo_domingo_octubre = d
            break
    
    if primer_domingo_abril is None:
        primer_domingo_abril = 7
    if ultimo_domingo_octubre is None:
        ultimo_domingo_octubre = 25
    
    sabado_antes_abril = primer_domingo_abril - 1
    if (mes == 2) or (mes == 3) or (mes == 4 and dia <= sabado_antes_abril):
        return 1
    if (mes == 4 and dia >= primer_domingo_abril) or (mes in [5, 6]) or (mes == 7):
        return 2
    sabado_antes_octubre = ultimo_domingo_octubre - 1
    if (mes == 8) or (mes == 9) or (mes == 10 and dia <= sabado_antes_octubre):
        return 3
    return 4

def es_festivo(fecha):
    """Determina si una fecha es festivo"""
    festivos_fijos = [(1, 1), (2, 5), (3, 21), (5, 1), (9, 16), (11, 20), (12, 25)]
    return (fecha.month, fecha.day) in festivos_fijos

def obtener_periodo_por_hora(fecha, hora_archivo):
    """Determina el periodo (Base, Intermedio, Punta) según la tabla oficial"""
    hora = hora_archivo - 1
    if hora == 24:
        hora = 0
    
    temporada = obtener_temporada(fecha)
    dia_semana = fecha.weekday()
    es_domingo = (dia_semana == 6)
    es_sabado = (dia_semana == 5)
    es_fest = es_festivo(fecha)
    
    if es_domingo or es_fest:
        if temporada == 1 or temporada == 3:
            if 0 <= hora <= 18 or hora == 23:
                return 'Base'
            else:
                return 'Intermedio'
        elif temporada == 2:
            if 0 <= hora <= 18:
                return 'Base'
            else:
                return 'Intermedio'
        else:
            if 0 <= hora <= 17:
                return 'Base'
            else:
                return 'Intermedio'
    elif es_sabado:
        if temporada == 1 or temporada == 3:
            if 0 <= hora <= 6:
                return 'Base'
            else:
                return 'Intermedio'
        elif temporada == 2:
            if hora == 0:
                return 'Intermedio'
            elif 1 <= hora <= 6:
                return 'Base'
            else:
                return 'Intermedio'
        else:
            if 0 <= hora <= 7:
                return 'Base'
            elif 8 <= hora <= 18:
                return 'Intermedio'
            elif 19 <= hora <= 20:
                return 'Punta'
            else:
                return 'Intermedio'
    else:
        if temporada == 1 or temporada == 3:
            if 0 <= hora <= 5:
                return 'Base'
            elif 6 <= hora <= 18:
                return 'Intermedio'
            elif 19 <= hora <= 21:
                return 'Punta'
            else:
                return 'Intermedio'
        elif temporada == 2:
            if hora == 0:
                return 'Intermedio'
            elif 1 <= hora <= 5:
                return 'Base'
            elif 6 <= hora <= 19:
                return 'Intermedio'
            elif 20 <= hora <= 21:
                return 'Punta'
            else:
                return 'Intermedio'
        else:
            if 0 <= hora <= 5:
                return 'Base'
            elif 6 <= hora <= 17:
                return 'Intermedio'
            elif 18 <= hora <= 21:
                return 'Punta'
            else:
                return 'Intermedio'

def leer_sin_agrupar(ruta_archivo):
    """Lee el archivo original SIN agrupar"""
    df = pd.read_csv(ruta_archivo, encoding='utf-8-sig')
    columna_fecha = df.columns[0]
    df['DATETIME'] = pd.to_datetime(df[columna_fecha], format='%d/%m/%Y %H:%M', errors='coerce')
    df = df.dropna(subset=['DATETIME']).reset_index(drop=True)
    
    col_kwh_rec = df.columns[1]
    col_kwh_ent = df.columns[2]
    df['KWH_REC'] = pd.to_numeric(df[col_kwh_rec], errors='coerce').fillna(0)
    df['KWH_ENT'] = pd.to_numeric(df[col_kwh_ent], errors='coerce').fillna(0)
    
    df['FECHA_HORA'] = df['DATETIME'].dt.strftime('%d/%m/%Y %H:%M')
    
    return df[['FECHA_HORA', 'KWH_REC', 'KWH_ENT']]

def leer_y_agrupar_por_hora(ruta_archivo, nombre_archivo):
    """Lee y agrupa datos por hora"""
    df = pd.read_csv(ruta_archivo, encoding='utf-8-sig')
    columna_fecha = df.columns[0]
    df['DATETIME'] = pd.to_datetime(df[columna_fecha], format='%d/%m/%Y %H:%M', errors='coerce')
    df = df.dropna(subset=['DATETIME']).reset_index(drop=True)
    
    col_kwh_rec = df.columns[1]
    col_kwh_ent = df.columns[2]
    df['KWH_REC'] = pd.to_numeric(df[col_kwh_rec], errors='coerce').fillna(0)
    df['KWH_ENT'] = pd.to_numeric(df[col_kwh_ent], errors='coerce').fillna(0)
    
    df = df.sort_values('DATETIME').reset_index(drop=True)
    num_registros = len(df)
    num_horas = num_registros // 12
    
    if num_registros % 12 != 0:
        print(f"  - ADVERTENCIA: {num_registros % 12} registros sobrantes en {nombre_archivo}")
        df = df.iloc[:num_horas * 12].reset_index(drop=True)
    
    df['GRUPO'] = np.arange(len(df)) // 12
    
    df_agrupado = df.groupby('GRUPO').agg({
        'DATETIME': 'first',
        'KWH_REC': 'sum',
        'KWH_ENT': 'sum'
    }).reset_index(drop=True)
    
    df_agrupado['HORA'] = df_agrupado['DATETIME'].dt.hour + 1
    df_agrupado['HORA'] = df_agrupado['HORA'].replace(25, 1)
    df_agrupado['FECHA'] = df_agrupado['DATETIME'].dt.strftime('%d/%m/%Y')
    df_agrupado['FECHA_HORA'] = df_agrupado['DATETIME'].dt.strftime('%d/%m/%Y %H:%M')
    
    return df_agrupado[['FECHA', 'HORA', 'FECHA_HORA', 'KWH_REC', 'KWH_ENT']]

def agregar_periodo(df):
    """Agrega la columna PERIODO a un dataframe"""
    periodos = []
    for idx, row in df.iterrows():
        fecha = datetime.strptime(row['FECHA'], '%d/%m/%Y')
        hora = row['HORA']
        periodo = obtener_periodo_por_hora(fecha, hora)
        periodos.append(periodo)
    df['PERIODO'] = periodos
    return df

def generar_combinado_por_minuto(ruta_bess, ruta_medidor, prefijo):
    """Genera COMBINADO_POR_MINUTO.csv con resolución de 5 minutos"""
    print("\n" + "=" * 60)
    print(f"GENERANDO COMBINADO_POR_MINUTO_{prefijo}.csv")
    print("=" * 60)
    
    df_bess = leer_sin_agrupar(ruta_bess)
    df_medidor = leer_sin_agrupar(ruta_medidor)
    
    print(f"  BESS: {len(df_bess)} registros")
    print(f"  {prefijo}: {len(df_medidor)} registros")
    
    df_combinado = pd.merge(
        df_bess[['FECHA_HORA', 'KWH_REC', 'KWH_ENT']],
        df_medidor[['FECHA_HORA', 'KWH_REC', 'KWH_ENT']],
        on='FECHA_HORA',
        suffixes=('_BESS', f'_{prefijo}'),
        how='inner'
    )
    
    print(f"  Registros combinados: {len(df_combinado)}")
    
    horas = []
    for idx, row in df_combinado.iterrows():
        dt = datetime.strptime(row['FECHA_HORA'], '%d/%m/%Y %H:%M')
        hora = dt.hour
        if hora == 0:
            hora = 24
        horas.append(hora)
    df_combinado['HORA'] = horas
    
    periodos = []
    for idx, row in df_combinado.iterrows():
        periodo = obtener_periodo_por_fecha_hora(row['FECHA_HORA'])
        periodos.append(periodo)
    df_combinado['PERIODO'] = periodos
    
    df_combinado['BESS_REC_kW'] = df_combinado['KWH_REC_BESS'] * 12
    df_combinado['BESS_ENT_kW'] = df_combinado['KWH_ENT_BESS'] * 12
    df_combinado[f'{prefijo}_REC_kW'] = df_combinado[f'KWH_REC_{prefijo}'] * 12
    df_combinado[f'{prefijo}_ENT_kW'] = df_combinado[f'KWH_ENT_{prefijo}'] * 12
    
    df_combinado[f'IUSA_CON_BESS_{prefijo}_kW'] = df_combinado[f'{prefijo}_REC_kW']
    df_combinado[f'IUSA_SIN_BESS_{prefijo}_kW'] = df_combinado[f'{prefijo}_REC_kW'] - df_combinado['BESS_REC_kW'] + df_combinado['BESS_ENT_kW']
    
    df_combinado['BESS_NETO_kWh'] = df_combinado['KWH_REC_BESS'] - df_combinado['KWH_ENT_BESS']
    df_combinado[f'{prefijo}_NETO_kWh'] = df_combinado[f'KWH_REC_{prefijo}'] - df_combinado[f'KWH_ENT_{prefijo}']
    df_combinado[f'Mejora_BESS_{prefijo}_kWh'] = df_combinado[f'{prefijo}_NETO_kWh'] - df_combinado['BESS_NETO_kWh']
    df_combinado[f'Mejora_BESS_{prefijo}_kW'] = df_combinado[f'Mejora_BESS_{prefijo}_kWh'] * 12
    
    print("\n--- Calculando demanda rodante (rolling demand 15 minutos) ---")
    columnas_kw = [col for col in df_combinado.columns if 'kW' in col and not col.endswith('_DEM_15min')]
    ventana = 15
    registros_ventana = ventana // 5
    
    for col in columnas_kw:
        col_demanda = f"{col}_DEM_15min"
        df_combinado[col_demanda] = df_combinado[col].rolling(
            window=registros_ventana,
            min_periods=registros_ventana
        ).mean()
    
    columnas_originales = [
        'FECHA_HORA', 'HORA', 'PERIODO',
        'KWH_REC_BESS', 'KWH_ENT_BESS', 'BESS_REC_kW', 'BESS_ENT_kW',
        f'KWH_REC_{prefijo}', f'KWH_ENT_{prefijo}', f'{prefijo}_REC_kW', f'{prefijo}_ENT_kW',
        'BESS_NETO_kWh', f'{prefijo}_NETO_kWh', f'Mejora_BESS_{prefijo}_kWh', f'Mejora_BESS_{prefijo}_kW',
        f'IUSA_CON_BESS_{prefijo}_kW', f'IUSA_SIN_BESS_{prefijo}_kW'
    ]
    
    columnas_demanda = [col for col in df_combinado.columns if 'DEM_' in col]
    df_combinado = df_combinado[columnas_originales + columnas_demanda]
    
    nombre_archivo = f'COMBINADO_POR_MINUTO_{prefijo}.csv'
    ruta_salida = os.path.join(DIRECTORIO_REPORTES, nombre_archivo)
    df_combinado.to_csv(ruta_salida, index=False)
    
    print(f"OK {nombre_archivo} - {len(df_combinado)} registros")
    return df_combinado

def obtener_periodo_por_fecha_hora(fecha_hora_str):
    """Determina el periodo según fecha y hora exacta"""
    dt = datetime.strptime(fecha_hora_str, '%d/%m/%Y %H:%M')
    fecha = dt.date()
    hora = dt.hour
    minuto = dt.minute
    
    hora_base = hora if minuto == 0 else hora + 1
    if hora_base == 24:
        hora_base = 0
        fecha = fecha + timedelta(days=1)
    
    return obtener_periodo_por_hora(fecha, hora_base if hora_base > 0 else 24)

def generar_diarios_con_demandas(prefijo):
    """Genera archivos diarios con demandas máximas"""
    print("\n" + "=" * 60)
    print(f"GENERANDO ARCHIVOS DIARIOS ({prefijo}) CON DEMANDAS MAXIMAS")
    print("=" * 60)
    
    ruta_med_hora = os.path.join(DIRECTORIO_REPORTES, f'ENERGIA_{prefijo}_POR_HORA.csv')
    ruta_minuto = os.path.join(DIRECTORIO_REPORTES, f'COMBINADO_POR_MINUTO_{prefijo}.csv')
    
    if not os.path.exists(ruta_med_hora) or not os.path.exists(ruta_minuto):
        print(f"ERROR: Faltan archivos para {prefijo}")
        return None
    
    df_medidor_hora = pd.read_csv(ruta_med_hora)
    df_minuto = pd.read_csv(ruta_minuto)
    df_minuto['FECHA'] = pd.to_datetime(df_minuto['FECHA_HORA'], format='%d/%m/%Y %H:%M').dt.strftime('%d/%m/%Y')
    
    # Energías diarias del medidor
    df_med_ent = df_medidor_hora.groupby(['FECHA', 'PERIODO'])['KWH_ENT'].sum().reset_index()
    df_med_ent_pivot = df_med_ent.pivot_table(index='FECHA', columns='PERIODO', values='KWH_ENT', aggfunc='sum', fill_value=0).reset_index()
    df_med_ent_pivot = df_med_ent_pivot.rename(columns={'Base': 'BASE_ENT', 'Intermedio': 'INTERMEDIO_ENT', 'Punta': 'PUNTA_ENT'})
    
    df_med_rec = df_medidor_hora.groupby(['FECHA', 'PERIODO'])['KWH_REC'].sum().reset_index()
    df_med_rec_pivot = df_med_rec.pivot_table(index='FECHA', columns='PERIODO', values='KWH_REC', aggfunc='sum', fill_value=0).reset_index()
    df_med_rec_pivot = df_med_rec_pivot.rename(columns={'Base': 'BASE_REC', 'Intermedio': 'INTERMEDIO_REC', 'Punta': 'PUNTA_REC'})
    
    df_med_diario = df_med_ent_pivot.merge(df_med_rec_pivot, on='FECHA', how='outer').fillna(0)
    
    # Demandas máximas IUSA_CON_BESS
    idx_con_max = df_minuto.groupby(['FECHA', 'PERIODO'])[f'IUSA_CON_BESS_{prefijo}_kW_DEM_15min'].idxmax()
    df_con_max = df_minuto.loc[idx_con_max, ['FECHA', 'PERIODO', f'IUSA_CON_BESS_{prefijo}_kW_DEM_15min', 'FECHA_HORA']].reset_index(drop=True)
    
    df_con_max_kw = df_con_max.pivot_table(index='FECHA', columns='PERIODO', values=f'IUSA_CON_BESS_{prefijo}_kW_DEM_15min', aggfunc='max', fill_value=0).reset_index()
    df_con_max_kw = df_con_max_kw.rename(columns={'Base': 'BASE_DEM_CON_BESS', 'Intermedio': 'INTERMEDIO_DEM_CON_BESS', 'Punta': 'PUNTA_DEM_CON_BESS'})
    
    df_con_max_fh = df_con_max.pivot_table(index='FECHA', columns='PERIODO', values='FECHA_HORA', aggfunc='first', fill_value='').reset_index()
    df_con_max_fh = df_con_max_fh.rename(columns={'Base': 'BASE_DEM_CON_BESS_FECHA_HORA', 'Intermedio': 'INTERMEDIO_DEM_CON_BESS_FECHA_HORA', 'Punta': 'PUNTA_DEM_CON_BESS_FECHA_HORA'})
    
    # Demandas máximas IUSA_SIN_BESS
    idx_sin_max = df_minuto.groupby(['FECHA', 'PERIODO'])[f'IUSA_SIN_BESS_{prefijo}_kW_DEM_15min'].idxmax()
    df_sin_max = df_minuto.loc[idx_sin_max, ['FECHA', 'PERIODO', f'IUSA_SIN_BESS_{prefijo}_kW_DEM_15min', 'FECHA_HORA']].reset_index(drop=True)
    
    df_sin_max_kw = df_sin_max.pivot_table(index='FECHA', columns='PERIODO', values=f'IUSA_SIN_BESS_{prefijo}_kW_DEM_15min', aggfunc='max', fill_value=0).reset_index()
    df_sin_max_kw = df_sin_max_kw.rename(columns={'Base': 'BASE_DEM_SIN_BESS', 'Intermedio': 'INTERMEDIO_DEM_SIN_BESS', 'Punta': 'PUNTA_DEM_SIN_BESS'})
    
    df_sin_max_fh = df_sin_max.pivot_table(index='FECHA', columns='PERIODO', values='FECHA_HORA', aggfunc='first', fill_value='').reset_index()
    df_sin_max_fh = df_sin_max_fh.rename(columns={'Base': 'BASE_DEM_SIN_BESS_FECHA_HORA', 'Intermedio': 'INTERMEDIO_DEM_SIN_BESS_FECHA_HORA', 'Punta': 'PUNTA_DEM_SIN_BESS_FECHA_HORA'})
    
    for df_temp in [df_con_max_kw, df_con_max_fh, df_sin_max_kw, df_sin_max_fh]:
        df_med_diario = df_med_diario.merge(df_temp, on='FECHA', how='left').fillna(0 if 'DEM' in df_temp.columns[1] else '')
    
    columnas_med = ['FECHA', 'BASE_ENT', 'INTERMEDIO_ENT', 'PUNTA_ENT', 'BASE_REC', 'INTERMEDIO_REC', 'PUNTA_REC',
                    'BASE_DEM_CON_BESS', 'BASE_DEM_CON_BESS_FECHA_HORA', 'INTERMEDIO_DEM_CON_BESS', 'INTERMEDIO_DEM_CON_BESS_FECHA_HORA',
                    'PUNTA_DEM_CON_BESS', 'PUNTA_DEM_CON_BESS_FECHA_HORA', 'BASE_DEM_SIN_BESS', 'BASE_DEM_SIN_BESS_FECHA_HORA',
                    'INTERMEDIO_DEM_SIN_BESS', 'INTERMEDIO_DEM_SIN_BESS_FECHA_HORA', 'PUNTA_DEM_SIN_BESS', 'PUNTA_DEM_SIN_BESS_FECHA_HORA']
    
    df_med_diario = df_med_diario[columnas_med]
    df_med_diario['FECHA_DT'] = pd.to_datetime(df_med_diario['FECHA'], format='%d/%m/%Y')
    df_med_diario = df_med_diario.sort_values('FECHA_DT').drop('FECHA_DT', axis=1)
    
    nombre_med_dia = f'ENERGIA_{prefijo}_POR_DIA.csv'
    ruta_salida = os.path.join(DIRECTORIO_REPORTES, nombre_med_dia)
    df_med_diario.to_csv(ruta_salida, index=False)
    print(f"OK {nombre_med_dia} - {len(df_med_diario)} dias")
    
    return df_med_diario

def generar_acumulados(prefijo):
    """Genera archivos acumulados por mes"""
    print("\n" + "=" * 60)
    print(f"GENERANDO ARCHIVOS ACUMULADOS ({prefijo})")
    print("=" * 60)
    
    ruta_med_dia = os.path.join(DIRECTORIO_REPORTES, f'ENERGIA_{prefijo}_POR_DIA.csv')
    
    if not os.path.exists(ruta_med_dia):
        print(f"ERROR: No se encuentra {ruta_med_dia}")
        return None
    
    df_med_dia = pd.read_csv(ruta_med_dia)
    df_med_dia['FECHA_DT'] = pd.to_datetime(df_med_dia['FECHA'], format='%d/%m/%Y')
    df_med_dia = df_med_dia.sort_values('FECHA_DT').reset_index(drop=True)
    df_med_dia['MES'] = df_med_dia['FECHA_DT'].dt.to_period('M')
    
    df_acum_med = pd.DataFrame()
    df_acum_med['FECHA'] = df_med_dia['FECHA']
    
    cols_energia = ['BASE_ENT', 'INTERMEDIO_ENT', 'PUNTA_ENT', 'BASE_REC', 'INTERMEDIO_REC', 'PUNTA_REC']
    for col in cols_energia:
        df_acum_med[f"{col}_ACUM"] = df_med_dia.groupby('MES')[col].cumsum()
    
    cols_demanda = ['BASE_DEM_CON_BESS', 'INTERMEDIO_DEM_CON_BESS', 'PUNTA_DEM_CON_BESS']
    cols_fechahora = [f"{col}_FECHA_HORA" for col in cols_demanda]
    
    for col_valor, col_fh in zip(cols_demanda, cols_fechahora):
        max_valor = 0
        max_fh = ""
        mes_actual = None
        valores = []
        fechahoras = []
        
        for idx, row in df_med_dia.iterrows():
            mes_row = row['MES']
            if mes_actual != mes_row:
                max_valor = 0
                max_fh = ""
                mes_actual = mes_row
            
            valor_actual = row[col_valor]
            fh_actual = row[col_fh]
            if valor_actual > max_valor:
                max_valor = valor_actual
                max_fh = fh_actual
            
            valores.append(max_valor)
            fechahoras.append(max_fh)
        
        df_acum_med[f"{col_valor}_MAX"] = valores
        df_acum_med[f"{col_valor}_MAX_FECHA_HORA"] = fechahoras
    
    nombre_med_acum = f'ACUMULADOS_{prefijo}.csv'
    ruta_salida = os.path.join(DIRECTORIO_REPORTES, nombre_med_acum)
    df_acum_med.to_csv(ruta_salida, index=False)
    print(f"OK {nombre_med_acum} - {len(df_acum_med)} dias (acumulado por mes)")
    
    return df_acum_med

def generar_bess_diario():
    """Genera ENERGIA_BESS_POR_DIA.csv"""
    print("\n" + "=" * 60)
    print("GENERANDO ENERGIA_BESS_POR_DIA.csv")
    print("=" * 60)
    
    ruta_bess_hora = os.path.join(DIRECTORIO_REPORTES, 'ENERGIA_BESS_POR_HORA.csv')
    
    if not os.path.exists(ruta_bess_hora):
        print("ERROR: No se encuentra ENERGIA_BESS_POR_HORA.csv")
        return None
    
    df_bess_hora = pd.read_csv(ruta_bess_hora)
    
    df_bess_dia = df_bess_hora.groupby(['FECHA', 'PERIODO']).agg({
        'KWH_REC': 'sum',
        'KWH_ENT': 'sum'
    }).reset_index()
    
    df_bess_rec_pivot = df_bess_dia.pivot_table(
        index='FECHA', columns='PERIODO', values='KWH_REC', aggfunc='sum', fill_value=0
    ).reset_index()
    df_bess_rec_pivot = df_bess_rec_pivot.rename(columns={
        'Base': 'BASE_REC', 'Intermedio': 'INTERMEDIO_REC', 'Punta': 'PUNTA_REC'
    })
    
    df_bess_ent_pivot = df_bess_dia.pivot_table(
        index='FECHA', columns='PERIODO', values='KWH_ENT', aggfunc='sum', fill_value=0
    ).reset_index()
    df_bess_ent_pivot = df_bess_ent_pivot.rename(columns={
        'Base': 'BASE_ENT', 'Intermedio': 'INTERMEDIO_ENT', 'Punta': 'PUNTA_ENT'
    })
    
    df_bess_diario = df_bess_rec_pivot.merge(df_bess_ent_pivot, on='FECHA', how='outer').fillna(0)
    df_bess_diario['FECHA_DT'] = pd.to_datetime(df_bess_diario['FECHA'], format='%d/%m/%Y')
    df_bess_diario = df_bess_diario.sort_values('FECHA_DT').drop('FECHA_DT', axis=1)
    
    ruta_salida = os.path.join(DIRECTORIO_REPORTES, 'ENERGIA_BESS_POR_DIA.csv')
    df_bess_diario.to_csv(ruta_salida, index=False)
    print(f"OK ENERGIA_BESS_POR_DIA.csv - {len(df_bess_diario)} dias")
    
    return df_bess_diario

def generar_acumulados_bess():
    """Genera ACUMULADOS_BESS.csv"""
    print("\n" + "=" * 60)
    print("GENERANDO ACUMULADOS_BESS.csv")
    print("=" * 60)
    
    ruta_bess_dia = os.path.join(DIRECTORIO_REPORTES, 'ENERGIA_BESS_POR_DIA.csv')
    
    if not os.path.exists(ruta_bess_dia):
        print("ERROR: No se encuentra ENERGIA_BESS_POR_DIA.csv")
        return None
    
    df_bess_diario = pd.read_csv(ruta_bess_dia)
    df_bess_diario['FECHA_DT'] = pd.to_datetime(df_bess_diario['FECHA'], format='%d/%m/%Y')
    df_bess_diario = df_bess_diario.sort_values('FECHA_DT').reset_index(drop=True)
    df_bess_diario['MES'] = df_bess_diario['FECHA_DT'].dt.to_period('M')
    
    df_acum_bess = pd.DataFrame()
    df_acum_bess['FECHA'] = df_bess_diario['FECHA']
    
    cols_energia = ['BASE_REC', 'INTERMEDIO_REC', 'PUNTA_REC', 'BASE_ENT', 'INTERMEDIO_ENT', 'PUNTA_ENT']
    for col in cols_energia:
        df_acum_bess[f"{col}_ACUM"] = df_bess_diario.groupby('MES')[col].cumsum()
    
    ruta_salida = os.path.join(DIRECTORIO_REPORTES, 'ACUMULADOS_BESS.csv')
    df_acum_bess.to_csv(ruta_salida, index=False)
    print(f"OK ACUMULADOS_BESS.csv - {len(df_acum_bess)} dias (acumulado por mes)")
    
    return df_acum_bess

def procesar_grupo(ruta_bess, ruta_medidor, prefijo, nombre_medidor, generar_bess_general=False):
    """Procesa un grupo de archivos (BESS + Medidor)"""
    print("\n" + "=" * 70)
    print(f"PROCESANDO GRUPO: BESS vs {nombre_medidor}")
    print("=" * 70)
    
    if not os.path.exists(ruta_bess):
        print(f"ERROR: No se encuentra el archivo BESS: {ruta_bess}")
        return False
    
    if not os.path.exists(ruta_medidor):
        print(f"ERROR: No se encuentra el archivo {nombre_medidor}: {ruta_medidor}")
        return False
    
    print(f"\n--- LECTURA Y AGRUPACION POR HORA ({prefijo}) ---")
    df_bess_hora = leer_y_agrupar_por_hora(ruta_bess, f'BESS_{prefijo}')
    df_medidor_hora = leer_y_agrupar_por_hora(ruta_medidor, nombre_medidor)
    
    if len(df_bess_hora) == 0 or len(df_medidor_hora) == 0:
        print(f"No se pudieron cargar datos validos para {prefijo}")
        return False
    
    print(f"\n--- AGREGANDO PERIODO ({prefijo}) ---")
    df_bess_hora_con_periodo = agregar_periodo(df_bess_hora.copy())
    df_medidor_hora_con_periodo = agregar_periodo(df_medidor_hora.copy())
    
    print(f"\n--- GENERANDO ARCHIVOS DE ENERGIA POR HORA ({prefijo}) ---")
    
    df_bess_output = df_bess_hora_con_periodo[['FECHA', 'HORA', 'KWH_REC', 'KWH_ENT', 'PERIODO']].copy()
    nombre_bess_hora = f'ENERGIA_BESS_POR_HORA_{prefijo}.csv'
    ruta_salida = os.path.join(DIRECTORIO_REPORTES, nombre_bess_hora)
    df_bess_output.to_csv(ruta_salida, index=False)
    print(f"OK {nombre_bess_hora} - {len(df_bess_output)} registros")
    
    if generar_bess_general:
        ruta_general = os.path.join(DIRECTORIO_REPORTES, 'ENERGIA_BESS_POR_HORA.csv')
        df_bess_output.to_csv(ruta_general, index=False)
        print(f"OK ENERGIA_BESS_POR_HORA.csv - {len(df_bess_output)} registros (archivo general)")
    
    df_medidor_output = df_medidor_hora_con_periodo[['FECHA', 'HORA', 'KWH_REC', 'KWH_ENT', 'PERIODO']].copy()
    nombre_med_hora = f'ENERGIA_{prefijo}_POR_HORA.csv'
    ruta_salida = os.path.join(DIRECTORIO_REPORTES, nombre_med_hora)
    df_medidor_output.to_csv(ruta_salida, index=False)
    print(f"OK {nombre_med_hora} - {len(df_medidor_output)} registros")
    
    print(f"\n--- GENERANDO COMBINADO_POR_HORA_{prefijo}.csv ---")
    df_combinado_hora = pd.merge(
        df_bess_hora[['FECHA_HORA', 'KWH_REC', 'KWH_ENT']],
        df_medidor_hora[['FECHA_HORA', 'KWH_REC', 'KWH_ENT']],
        on='FECHA_HORA',
        suffixes=('_BESS', f'_{prefijo}'),
        how='inner'
    )
    
    horas = []
    periodos = []
    for idx, row in df_combinado_hora.iterrows():
        fecha_hora = datetime.strptime(row['FECHA_HORA'], '%d/%m/%Y %H:%M')
        hora = fecha_hora.hour
        if hora == 0:
            hora = 24
        horas.append(hora)
        fecha_periodo = fecha_hora
        if fecha_hora.hour == 0 and fecha_hora.minute == 0:
            fecha_periodo = fecha_periodo - timedelta(days=1)
        periodo = obtener_periodo_por_hora(fecha_periodo, hora)
        periodos.append(periodo)
    
    df_combinado_hora['HORA'] = horas
    df_combinado_hora['PERIODO'] = periodos
    df_combinado_hora['BESS_REC_kW'] = df_combinado_hora['KWH_REC_BESS'] * 12
    df_combinado_hora['BESS_ENT_kW'] = df_combinado_hora['KWH_ENT_BESS'] * 12
    df_combinado_hora[f'{prefijo}_REC_kW'] = df_combinado_hora[f'KWH_REC_{prefijo}'] * 12
    df_combinado_hora[f'{prefijo}_ENT_kW'] = df_combinado_hora[f'KWH_ENT_{prefijo}'] * 12
    df_combinado_hora[f'IUSA_CON_BESS_{prefijo}_kW'] = df_combinado_hora[f'{prefijo}_REC_kW']
    df_combinado_hora[f'IUSA_SIN_BESS_{prefijo}_kW'] = df_combinado_hora[f'{prefijo}_REC_kW'] - df_combinado_hora['BESS_REC_kW'] + df_combinado_hora['BESS_ENT_kW']
    df_combinado_hora['BESS_NETO_kWh'] = df_combinado_hora['KWH_REC_BESS'] - df_combinado_hora['KWH_ENT_BESS']
    df_combinado_hora[f'{prefijo}_NETO_kWh'] = df_combinado_hora[f'KWH_REC_{prefijo}'] - df_combinado_hora[f'KWH_ENT_{prefijo}']
    df_combinado_hora[f'Mejora_BESS_{prefijo}_kWh'] = df_combinado_hora[f'{prefijo}_NETO_kWh'] - df_combinado_hora['BESS_NETO_kWh']
    df_combinado_hora[f'Mejora_BESS_{prefijo}_kW'] = df_combinado_hora[f'Mejora_BESS_{prefijo}_kWh'] * 12
    
    columnas_hora = ['FECHA_HORA', 'HORA', 'PERIODO', 'KWH_REC_BESS', 'KWH_ENT_BESS', 'BESS_REC_kW', 'BESS_ENT_kW',
                     f'KWH_REC_{prefijo}', f'KWH_ENT_{prefijo}', f'{prefijo}_REC_kW', f'{prefijo}_ENT_kW',
                     'BESS_NETO_kWh', f'{prefijo}_NETO_kWh', f'Mejora_BESS_{prefijo}_kWh', f'Mejora_BESS_{prefijo}_kW',
                     f'IUSA_CON_BESS_{prefijo}_kW', f'IUSA_SIN_BESS_{prefijo}_kW']
    
    nombre_comb_hora = f'COMBINADO_POR_HORA_{prefijo}.csv'
    ruta_salida = os.path.join(DIRECTORIO_REPORTES, nombre_comb_hora)
    df_combinado_hora[columnas_hora].to_csv(ruta_salida, index=False)
    print(f"OK {nombre_comb_hora} - {len(df_combinado_hora)} registros")
    
    generar_combinado_por_minuto(ruta_bess, ruta_medidor, prefijo)
    generar_diarios_con_demandas(prefijo)
    generar_acumulados(prefijo)
    
    print(f"\nOK Grupo {prefijo} procesado exitosamente")
    return True

def reporte_bess():
    """Función principal de ReporteBESS"""
    print("=" * 60)
    print("PROCESAMIENTO DE DATOS DE ENERGIA - REGION CENTRAL")
    print("PROCESAMIENTO DE DOS GRUPOS: BESS vs ION y BESS vs BANCO1")
    print("=" * 60)
    
    os.chdir(DIRECTORIO_REPORTES)
    
    RUTA_BESS = os.path.join(DIRECTORIO_PROCESADOS, 'BESS_Filtrado.csv')
    RUTA_ION = os.path.join(DIRECTORIO_PROCESADOS, 'ION_Filtrado.csv')
    RUTA_BANCO = os.path.join(DIRECTORIO_PROCESADOS, 'Banco1_Filtrado.csv')
    
    print(f"\nDirectorio de archivos fuente: {DIRECTORIO_PROCESADOS}")
    print(f"Directorio de reportes: {DIRECTORIO_REPORTES}")
    
    resultado_ion = procesar_grupo(RUTA_BESS, RUTA_ION, 'ION', 'ION', generar_bess_general=True)
    resultado_banco = procesar_grupo(RUTA_BESS, RUTA_BANCO, 'BANCO', 'Banco1', generar_bess_general=False)
    
    print("\n" + "=" * 60)
    print("GENERANDO ARCHIVOS GENERALES DEL BESS")
    print("=" * 60)
    
    if os.path.exists(os.path.join(DIRECTORIO_REPORTES, 'ENERGIA_BESS_POR_HORA.csv')):
        generar_bess_diario()
    else:
        print("No se encontro ENERGIA_BESS_POR_HORA.csv")
    
    if os.path.exists(os.path.join(DIRECTORIO_REPORTES, 'ENERGIA_BESS_POR_DIA.csv')):
        generar_acumulados_bess()
    else:
        print("No se encontro ENERGIA_BESS_POR_DIA.csv")
    
    print("\n" + "=" * 60)
    print("RESUMEN DEL PROCESO")
    print("=" * 60)
    print("\nGRUPO 1: BESS vs ION - " + ("✅ Éxito" if resultado_ion else "❌ Falló"))
    print("GRUPO 2: BESS vs BANCO1 - " + ("✅ Éxito" if resultado_banco else "❌ Falló"))
    print("\n" + "=" * 60)
    print("=== FIN DEL PROCESO ===")
    
    return resultado_ion and resultado_banco

# ========== PARTE 4: GENERA REPORTE PDF ==========

def get_mes_espanol(mes_numero):
    meses = {1: 'Enero', 2: 'Febrero', 3: 'Marzo', 4: 'Abril', 5: 'Mayo', 6: 'Junio',
             7: 'Julio', 8: 'Agosto', 9: 'Septiembre', 10: 'Octubre', 11: 'Noviembre', 12: 'Diciembre'}
    return meses.get(mes_numero, '')

def formatear_fecha_espanol(fecha_dt):
    dia = fecha_dt.day
    mes = get_mes_espanol(fecha_dt.month)
    ano = fecha_dt.year
    return f"{dia} de {mes} de {ano}"

def cargar_tarifas():
    """Carga las tarifas desde el archivo CSV"""
    ruta_tarifas = os.path.join(DIRECTORIO_TARIFAS, 'Tarifas_2026.csv')
    
    if not os.path.exists(ruta_tarifas):
        print("ADVERTENCIA: No se encontró el archivo de tarifas")
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
        
        print(f"Tarifas cargadas desde: {ruta_tarifas}")
        return tarifas
    except Exception as e:
        print(f"ADVERTENCIA: Error al cargar tarifas: {e}")
        return {'Base': {i: 0 for i in range(1, 13)}, 'Intermedio': {i: 0 for i in range(1, 13)}, 'Punta': {i: 0 for i in range(1, 13)}}

def cargar_datos_reporte(fecha_str, medidor):
    """Carga los datos para el reporte"""
    prefijo = 'ION' if medidor == 'ION' else 'BANCO'
    
    ruta_combinado = os.path.join(DIRECTORIO_REPORTES, f'COMBINADO_POR_MINUTO_{prefijo}.csv')
    ruta_acumulados = os.path.join(DIRECTORIO_REPORTES, f'ACUMULADOS_{prefijo}.csv')
    ruta_bess_dia = os.path.join(DIRECTORIO_REPORTES, 'ENERGIA_BESS_POR_DIA.csv')
    
    if not os.path.exists(ruta_combinado) or not os.path.exists(ruta_acumulados) or not os.path.exists(ruta_bess_dia):
        print(f"ERROR: Faltan archivos para {prefijo}")
        return None, None, None
    
    df_combinado = pd.read_csv(ruta_combinado)
    df_acumulados = pd.read_csv(ruta_acumulados)
    df_bess_dia = pd.read_csv(ruta_bess_dia)
    
    df_combinado['DATETIME'] = pd.to_datetime(df_combinado['FECHA_HORA'], format='%d/%m/%Y %H:%M')
    
    fecha_dt = datetime.strptime(fecha_str, '%d/%m/%Y')
    inicio = fecha_dt.replace(hour=0, minute=0, second=0)
    fin = (fecha_dt + timedelta(days=1)).replace(hour=0, minute=0, second=0)
    
    mask = (df_combinado['DATETIME'] >= inicio) & (df_combinado['DATETIME'] < fin)
    df_dia = df_combinado[mask].copy()
    df_dia = df_dia.sort_values('DATETIME').reset_index(drop=True)
    
    fila_acum = df_acumulados[df_acumulados['FECHA'] == fecha_str]
    fila_bess = df_bess_dia[df_bess_dia['FECHA'] == fecha_str]
    
    return df_dia, fila_acum, fila_bess

def generar_perfil_carga(df_dia, prefijo):
    """Genera la gráfica de Perfil de Carga"""
    fig, ax = plt.subplots(figsize=(14, 4.5), facecolor='white', dpi=150)
    ax.set_facecolor('#f0f2f5')
    
    fechas = df_dia['DATETIME'].values
    iusa_con = df_dia[f'IUSA_CON_BESS_{prefijo}_kW'].values
    bess_rec = df_dia['BESS_REC_kW'].values
    bess_ent = -df_dia['BESS_ENT_kW'].values
    
    color_iusa = '#0055a4'
    color_carga = '#00a86b'
    color_descarga = '#d62828'
    
    # CORRECCIÓN: fill_between desde el mínimo valor negativo hasta los valores
    # para que se vea toda el área incluyendo la parte negativa
    ax.fill_between(fechas, 0, iusa_con, alpha=0.3, color=color_iusa, label='_nolegend_')
    ax.fill_between(fechas, 0, bess_rec, alpha=0.3, color=color_carga, label='_nolegend_')
    ax.fill_between(fechas, bess_ent, 0, alpha=0.3, color=color_descarga, label='_nolegend_')  # CORREGIDO
    
    ax.plot(fechas, iusa_con, color=color_iusa, linewidth=2.5, label='IUSA 1 - Con BESS')
    ax.plot(fechas, bess_rec, color=color_carga, linewidth=2, label='Carga BESS')
    ax.plot(fechas, bess_ent, color=color_descarga, linewidth=2, label='Descarga BESS')
    
    ax.set_title('Perfil de Carga', fontsize=16, fontweight='bold', color='#1a1a1a', pad=20)
    ax.set_xlabel('Hora', fontsize=13, fontweight='bold', color='#2c3e50')
    ax.set_ylabel('Potencia (kW)', fontsize=13, fontweight='bold', color='#2c3e50')
    ax.tick_params(colors='#5d6d7e', labelsize=11)
    ax.grid(True, alpha=0.15, color='#bdc3c7', linestyle='-', linewidth=0.5)
    
    ax.xaxis.set_major_formatter(mdates.DateFormatter('%H:%M'))
    ax.xaxis.set_major_locator(mdates.HourLocator(interval=2))
    ax.xaxis.set_minor_locator(mdates.HourLocator(interval=1))
    plt.setp(ax.xaxis.get_majorticklabels(), rotation=45, ha='right')
    
    ax.spines['top'].set_visible(False)
    ax.spines['right'].set_visible(False)
    ax.spines['left'].set_color('#bdc3c7')
    ax.spines['bottom'].set_color('#bdc3c7')
    
    # CORRECCIÓN: Calcular límites incluyendo valores negativos
    max_valor = max(max(iusa_con), max(bess_rec), max(abs(bess_ent)))
    min_valor = min(min(iusa_con), min(bess_rec), min(bess_ent))
    
    # Establecer límites para mostrar valores negativos
    if min_valor < 0:
        ax.set_ylim(min_valor * 1.3, max_valor * 1.2)
    else:
        ax.set_ylim(min_valor * 0.12, max_valor * 1.12)
    
    ax.axhline(y=0, color='#95a5a6', linestyle='-', alpha=0.3, linewidth=1)
    
    legend = ax.legend(loc='upper center', fontsize=11, framealpha=0.95, edgecolor='#d5d8dc', ncol=3)
    legend.get_frame().set_facecolor('white')
    
    plt.tight_layout()
    
    buf = io.BytesIO()
    plt.savefig(buf, format='png', dpi=200, bbox_inches='tight', facecolor='white')
    buf.seek(0)
    plt.close()
    
    return buf

def buscar_logo():
    """Busca el logo en diferentes ubicaciones posibles"""
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

def generar_reporte_pdf(fecha_str, medidor='BANCO'):
    """Genera el reporte PDF"""
    prefijo = 'ION' if medidor == 'ION' else 'BANCO'
    
    df_dia, fila_acum, fila_bess = cargar_datos_reporte(fecha_str, medidor)
    
    if df_dia is None or len(df_dia) == 0:
        print(f"No hay datos para la fecha {fecha_str}")
        return False
    
    fecha_dt = datetime.strptime(fecha_str, '%d/%m/%Y')
    nombre_archivo = f'Reporte_{prefijo}_{fecha_dt.strftime("%Y%m%d")}.pdf'
    ruta_pdf = os.path.join(DIRECTORIO_REPORTES_DIARIOS, nombre_archivo)
    
    os.makedirs(DIRECTORIO_REPORTES_DIARIOS, exist_ok=True)
    
    # CORRECCIÓN: Reducir márgenes para más espacio
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
    
    # Logo - Tamaño ajustado
    logo_path = buscar_logo()
    if logo_path:
        try:
            img_logo = PILImage.open(logo_path)
            # CORRECCIÓN: Logo un poco más pequeño para dejar espacio
            logo_width = 1.8 * inch
            logo_height = logo_width * (img_logo.height / img_logo.width)
            logo_temp = os.path.join(DIRECTORIO_REPORTES_DIARIOS, 'temp_logo.png')
            img_logo.save(logo_temp, 'PNG', quality=95)
            archivos_temp.append(logo_temp)
            story.append(Image(logo_temp, width=logo_width, height=logo_height))
            story.append(Spacer(1, 0.02*inch))
        except Exception as e:
            print(f"ADVERTENCIA: Error al cargar el logo: {e}")
    
    fecha_espanol = formatear_fecha_espanol(fecha_dt)
    story.append(Paragraph("Pastejé, Jocotitlán, Estado de México", styles['CustomSubtitleRight']))
    story.append(Paragraph(f"Reporte del {fecha_espanol}", styles['CustomSubtitleRight']))
    story.append(Spacer(1, 0.05*inch))
    
    # CORRECCIÓN: Gráfica más grande
    buf = generar_perfil_carga(df_dia, prefijo)
    img_path = os.path.join(DIRECTORIO_REPORTES_DIARIOS, f'temp_perfil_{prefijo}_{fecha_dt.strftime("%Y%m%d")}.png')
    archivos_temp.append(img_path)
    img = PILImage.open(buf)
    img.save(img_path, 'PNG', quality=95, dpi=(200, 200))
    # Aumentado de 9.5 x 3.5 a 10.5 x 4.0 pulgadas
    story.append(Image(img_path, width=10.5*inch, height=4.0*inch))
    story.append(Spacer(1, 0.08*inch))
    
    # CORRECCIÓN: Tabla más grande y con mejor formato
    tarifas = cargar_tarifas()
    mes = fecha_dt.month
    
    data = [['Periodo', 'Base', 'Intermedio', 'Punta', 'Total']]
    
    if len(fila_acum) > 0:
        fila = fila_acum.iloc[0]
        consumo_base = int(fila.get('BASE_REC_ACUM', 0))
        consumo_intermedio = int(fila.get('INTERMEDIO_REC_ACUM', 0))
        consumo_punta = int(fila.get('PUNTA_REC_ACUM', 0))
        consumo_total = consumo_base + consumo_intermedio + consumo_punta
        
        demanda_base = int(np.ceil(fila.get('BASE_DEM_CON_BESS_MAX', 0)))
        demanda_intermedio = int(np.ceil(fila.get('INTERMEDIO_DEM_CON_BESS_MAX', 0)))
        demanda_punta = int(np.ceil(fila.get('PUNTA_DEM_CON_BESS_MAX', 0)))
    else:
        consumo_base = consumo_intermedio = consumo_punta = consumo_total = 0
        demanda_base = demanda_intermedio = demanda_punta = 0
    
    if len(fila_bess) > 0:
        fila = fila_bess.iloc[0]
        carga_base = int(fila.get('BASE_REC', 0))
        carga_intermedio = int(fila.get('INTERMEDIO_REC', 0))
        carga_punta = int(fila.get('PUNTA_REC', 0))
        carga_total = carga_base + carga_intermedio + carga_punta
        
        descarga_base = int(fila.get('BASE_ENT', 0))
        descarga_intermedio = int(fila.get('INTERMEDIO_ENT', 0))
        descarga_punta = int(fila.get('PUNTA_ENT', 0))
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
    
    # CORRECCIÓN: Tabla más ancha y con mejor estilo
    tabla = Table(data, colWidths=[2.5*inch, 1.3*inch, 1.3*inch, 1.3*inch, 1.3*inch])
    tabla.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#2c3e50')),
        ('TEXTCOLOR', (0, 0), (-1, 0), colors.white),
        ('ALIGN', (0, 0), (-1, 0), 'CENTER'),
        ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
        ('FONTSIZE', (0, 0), (-1, 0), 11),  # Aumentado de 10 a 11
        ('FONTNAME', (0, 1), (-1, -1), 'Helvetica'),
        ('FONTSIZE', (0, 1), (-1, -1), 10),  # Aumentado de 9 a 10
        ('ALIGN', (0, 1), (0, -1), 'LEFT'),
        ('ALIGN', (1, 1), (-1, -1), 'RIGHT'),
        ('BOX', (0, 0), (-1, -1), 1.5, colors.black),
        ('GRID', (0, 0), (-1, -1), 0.5, colors.HexColor('#d5d8dc')),
        ('FONTNAME', (4, 1), (4, -1), 'Helvetica-Bold'),
        ('LEFTPADDING', (0, 0), (-1, -1), 6),  # Aumentado de 4 a 6
        ('RIGHTPADDING', (0, 0), (-1, -1), 6),  # Aumentado de 4 a 6
        # CORRECCIÓN: Colores alternados para las filas
        ('BACKGROUND', (0, 1), (-1, 1), colors.HexColor('#f8f9fa')),
        ('BACKGROUND', (0, 3), (-1, 3), colors.HexColor('#f8f9fa')),
        ('BACKGROUND', (0, 5), (-1, 5), colors.HexColor('#f8f9fa')),
        # CORRECCIÓN: Resaltar fila de arbitraje
        ('BACKGROUND', (0, 5), (-1, 5), colors.HexColor('#e8f4f8')),
        ('FONTNAME', (0, 5), (-1, 5), 'Helvetica-Bold'),
    ]))
    story.append(tabla)
    story.append(Spacer(1, 0.1*inch))
    
    story.append(Paragraph("Carretera Panamericana Mexico Queretaro S/N km. 100, Pesteje, Jocotitlan, Estado de Mexico", styles['Footer']))
    
    doc.build(story)
    
    for archivo in archivos_temp:
        if os.path.exists(archivo):
            try:
                os.remove(archivo)
            except:
                pass
    
    print(f"Reporte generado: {ruta_pdf}")
    return True

def generar_reporte_desde_dashboard(fecha_str, medidor):
    """Genera reporte desde el dashboard (wrapper)"""
    return generar_reporte_pdf(fecha_str, medidor)

# ========== PARTE 5: DASHBOARD GRÁFICO ==========

# Variables globales para el dashboard
df_dashboard = None
dias_unicos = []
dias_unicos_str = []
MEDIDOR_ACTUAL = 'ION'

def cargar_datos_medidor_dashboard(medidor):
    """Carga los datos del medidor seleccionado"""
    global df_dashboard, dias_unicos, dias_unicos_str, MEDIDOR_ACTUAL
    
    MEDIDOR_ACTUAL = medidor
    prefijo = 'ION' if medidor == 'ION' else 'BANCO'
    nombre_archivo = f'COMBINADO_POR_MINUTO_{prefijo}.csv'
    ruta_archivo = os.path.join(DIRECTORIO_REPORTES, nombre_archivo)
    
    if not os.path.exists(ruta_archivo):
        print(f"Error: No se encuentra {nombre_archivo}")
        return False
    
    df_dashboard = pd.read_csv(ruta_archivo)
    
    columnas_numericas = ['KWH_REC_BESS', 'KWH_ENT_BESS', f'KWH_REC_{prefijo}', f'KWH_ENT_{prefijo}',
                         'BESS_REC_kW', 'BESS_ENT_kW', f'{prefijo}_REC_kW', f'{prefijo}_ENT_kW',
                         'BESS_NETO_kWh', f'{prefijo}_NETO_kWh', f'Mejora_BESS_{prefijo}_kWh',
                         f'Mejora_BESS_{prefijo}_kW', f'IUSA_CON_BESS_{prefijo}_kW',
                         f'IUSA_SIN_BESS_{prefijo}_kW']
    
    for col in columnas_numericas:
        if col in df_dashboard.columns:
            df_dashboard[col] = pd.to_numeric(df_dashboard[col], errors='coerce').fillna(0)
    
    df_dashboard['DATETIME'] = pd.to_datetime(df_dashboard['FECHA_HORA'], format='%d/%m/%Y %H:%M', errors='coerce')
    df_dashboard = df_dashboard.dropna(subset=['DATETIME']).reset_index(drop=True)
    
    dias_unicos = sorted(df_dashboard['DATETIME'].dt.date.unique())
    dias_unicos_str = [d.strftime('%d/%m/%Y') for d in dias_unicos]
    
    print(f"Total de dias disponibles: {len(dias_unicos)}")
    return True

class DashboardGraficas:
    def __init__(self, root):
        self.root = root
        self.root.title("Dashboard - Analisis de Energia BESS vs ION/BANCO")
        self.root.geometry("1500x950")
        self.root.configure(bg='#0f1923')
        
        self.ventana_activa = True
        self.root.protocol("WM_DELETE_WINDOW", self.cerrar_ventana)
        
        self.colores = {
            'bg': '#0f1923', 'frame': '#1a2a3a', 'frame_light': '#243544',
            'frame_header': '#0d1a2b', 'texto': '#e8edf2', 'texto_secundario': '#8a9ba8',
            'texto_titulo': '#00d4ff', 'acento': '#00d4ff', 'acento_hover': '#00a8cc',
            'exito': '#2ecc71', 'warning': '#f1c40f', 'peligro': '#e74c3c',
            'grafica': '#0f1923', 'linea1': '#00d4ff', 'linea2': '#2ecc71',
            'linea3': '#e74c3c', 'linea4': '#f1c40f'
        }
        
        self.fuentes = {
            'titulo': ('Segoe UI', 16, 'bold'),
            'subtitulo': ('Segoe UI', 12, 'bold'),
            'normal': ('Segoe UI', 9),
            'numeros': ('Consolas', 11, 'bold'),
            'boton': ('Segoe UI', 10, 'bold')
        }
        
        self.fecha_var = tk.StringVar()
        self.medidor_var = tk.StringVar(value=MEDIDOR_ACTUAL)
        self.tarifas = cargar_tarifas()
        self.timer_id = None
        self.fig_perfil = None
        self.ax_perfil = None
        self.canvas_perfil = None
        self.fig_individual = None
        self.ax_individual = None
        self.canvas_individual = None
        
        self.construir_interfaz()
        self.actualizar_reloj()
        self.actualizar_combo_fechas()
        
        if dias_unicos_str:
            self.fecha_var.set(dias_unicos_str[0])
            self.root.after(500, self.actualizar_todas_graficas)
    
    def cerrar_ventana(self):
        self.ventana_activa = False
        if self.timer_id:
            try:
                self.root.after_cancel(self.timer_id)
            except:
                pass
        try:
            plt.close('all')
        except:
            pass
        self.root.destroy()
    
    def crear_boton(self, parent, texto, comando, color=None):
        if color is None:
            color = self.colores['acento']
        btn = tk.Button(parent, text=texto, command=comando, bg=color, fg='white',
                       font=self.fuentes['boton'], relief=tk.FLAT, cursor='hand2',
                       padx=20, pady=8)
        btn.bind('<Enter>', lambda e: btn.config(bg=self.colores['acento_hover']))
        btn.bind('<Leave>', lambda e: btn.config(bg=color))
        return btn
    
    def construir_interfaz(self):
        main_frame = tk.Frame(self.root, bg=self.colores['bg'])
        main_frame.pack(fill=tk.BOTH, expand=True, padx=15, pady=15)
        
        # Panel de control (izquierda)
        panel_control = tk.Frame(main_frame, bg=self.colores['frame'], width=480)
        panel_control.pack(side=tk.LEFT, fill=tk.Y, padx=(0, 15))
        panel_control.pack_propagate(False)
        
        # Título
        titulo_frame = tk.Frame(panel_control, bg=self.colores['frame_header'])
        titulo_frame.pack(fill=tk.X, pady=(0, 10))
        tk.Label(titulo_frame, text="⚡ CONTROLES", font=self.fuentes['titulo'],
                fg=self.colores['texto_titulo'], bg=self.colores['frame_header']).pack(pady=15)
        
        # Selector de medidor
        tk.Label(panel_control, text="Seleccionar Medidor:", font=self.fuentes['normal'],
                fg=self.colores['texto_secundario'], bg=self.colores['frame']).pack(pady=(15, 5))
        
        frame_medidor = tk.Frame(panel_control, bg=self.colores['frame'])
        frame_medidor.pack(pady=5)
        
        self.btn_ion = tk.Button(frame_medidor, text="ION", 
                                command=lambda: self.cambiar_medidor('ION'),
                                bg='#00d4ff' if MEDIDOR_ACTUAL == 'ION' else '#2a3a4a',
                                fg='white', font=self.fuentes['boton'], relief=tk.FLAT,
                                cursor='hand2', width=12, padx=10, pady=6)
        self.btn_ion.pack(side=tk.LEFT, padx=5)
        
        self.btn_banco = tk.Button(frame_medidor, text="BANCO1",
                                command=lambda: self.cambiar_medidor('BANCO'),
                                bg='#00d4ff' if MEDIDOR_ACTUAL == 'BANCO' else '#2a3a4a',
                                fg='white', font=self.fuentes['boton'], relief=tk.FLAT,
                                cursor='hand2', width=12, padx=10, pady=6)
        self.btn_banco.pack(side=tk.LEFT, padx=5)
        
        # Separador
        tk.Frame(panel_control, height=2, bg=self.colores['frame_light']).pack(fill=tk.X, pady=15)
        
        # Selección de fecha
        tk.Label(panel_control, text="Seleccionar Fecha:", font=self.fuentes['normal'],
                fg=self.colores['texto_secundario'], bg=self.colores['frame']).pack(pady=(10, 5))
        
        self.combo_fecha = ttk.Combobox(panel_control, textvariable=self.fecha_var,
                                       values=dias_unicos_str, state='readonly',
                                       font=self.fuentes['normal'], width=35)
        self.combo_fecha.pack(pady=5)
        if dias_unicos_str:
            self.combo_fecha.set(dias_unicos_str[0])
        
        # Botones
        self.btn_actualizar = self.crear_boton(panel_control, "🔄 ACTUALIZAR GRAFICAS",
                                              self.actualizar_todas_graficas)
        self.btn_actualizar.pack(pady=15)
        
        self.btn_reporte = self.crear_boton(panel_control, "📄 GENERAR REPORTE PDF",
                                           lambda: self.generar_reporte_pdf(),
                                           '#2ecc71')
        self.btn_reporte.pack(pady=(5, 20))
        
        # Información del día
        info_frame = tk.Frame(panel_control, bg=self.colores['frame_light'])
        info_frame.pack(fill=tk.X, pady=10, padx=10)
        
        tk.Label(info_frame, text="📊 ESTADISTICAS DEL DIA", font=self.fuentes['subtitulo'],
                fg=self.colores['texto_titulo'], bg=self.colores['frame_light']).pack(pady=5)
        
        self.label_registros = tk.Label(info_frame, text="", font=self.fuentes['normal'],
                                       fg=self.colores['exito'], bg=self.colores['frame_light'])
        self.label_registros.pack()
        
        # Cuadro de información
        self.crear_cuadro_informacion(panel_control)
        
        # Área de gráficas (derecha)
        panel_graficas = tk.Frame(main_frame, bg=self.colores['bg'])
        panel_graficas.pack(side=tk.RIGHT, fill=tk.BOTH, expand=True)
        
        contenedor_graficas = tk.Frame(panel_graficas, bg=self.colores['bg'])
        contenedor_graficas.pack(fill=tk.BOTH, expand=True)
        contenedor_graficas.grid_rowconfigure(0, weight=1)
        contenedor_graficas.grid_rowconfigure(1, weight=1)
        contenedor_graficas.grid_columnconfigure(0, weight=1)
        
        # Gráfica 1: Comparación IUSA
        frame_individual = tk.LabelFrame(contenedor_graficas,
                                        text="📊 COMPARACIÓN IUSA",
                                        bg=self.colores['frame'],
                                        fg=self.colores['texto_titulo'],
                                        font=self.fuentes['subtitulo'])
        frame_individual.grid(row=0, column=0, sticky="nsew", padx=0, pady=2)
        
        self.fig_individual, self.ax_individual = plt.subplots(figsize=(10, 4.5),
                                                              facecolor=self.colores['grafica'])
        self.ax_individual.set_facecolor(self.colores['grafica'])
        self.canvas_individual = FigureCanvasTkAgg(self.fig_individual, frame_individual)
        self.canvas_individual.get_tk_widget().pack(fill=tk.BOTH, expand=True, padx=10, pady=5)
        
        # Gráfica 2: Perfil de Carga
        frame_perfil = tk.LabelFrame(contenedor_graficas,
                                    text="⚡ PERFIL DE CARGA",
                                    bg=self.colores['frame'],
                                    fg=self.colores['texto_titulo'],
                                    font=self.fuentes['subtitulo'])
        frame_perfil.grid(row=1, column=0, sticky="nsew", padx=0, pady=2)
        
        self.fig_perfil, self.ax_perfil = plt.subplots(figsize=(10, 4.5),
                                                      facecolor=self.colores['grafica'])
        self.ax_perfil.set_facecolor(self.colores['grafica'])
        self.canvas_perfil = FigureCanvasTkAgg(self.fig_perfil, frame_perfil)
        self.canvas_perfil.get_tk_widget().pack(fill=tk.BOTH, expand=True, padx=10, pady=5)
        
        # Barra de estado
        self.status_bar = tk.Label(self.root, text="Sistema listo",
                                  bg=self.colores['frame'], fg=self.colores['texto_secundario'],
                                  relief=tk.SUNKEN, anchor=tk.W, padx=15,
                                  font=('Segoe UI', 9))
        self.status_bar.pack(side=tk.BOTTOM, fill=tk.X)
    
    def crear_cuadro_informacion(self, parent):
        info_cuadro = tk.LabelFrame(parent, text="📊 RESUMEN DE ENERGIA",
                                   bg=self.colores['frame_light'],
                                   fg=self.colores['texto_titulo'],
                                   font=self.fuentes['subtitulo'])
        info_cuadro.pack(fill=tk.X, pady=10, padx=10, side=tk.BOTTOM)
        
        info_cuadro.grid_columnconfigure(0, weight=2)
        for i in range(1, 5):
            info_cuadro.grid_columnconfigure(i, weight=1)
        
        headers = ['Periodo', 'Base', 'Intermedio', 'Punta', 'Total']
        for col, header in enumerate(headers):
            tk.Label(info_cuadro, text=header, font=self.fuentes['subtitulo'],
                    fg=self.colores['texto_titulo'], bg=self.colores['frame_light'],
                    anchor='center', padx=5, pady=5).grid(row=0, column=col, sticky="ew")
        
        tk.Frame(info_cuadro, height=2, bg=self.colores['frame']).grid(
            row=1, column=0, columnspan=5, sticky="ew", pady=2)
        
        filas = [
            ('Consumo Mensual (kWh)', 'consumo', '#2ecc71'),
            ('Demanda Rolada (kW)', 'demanda', '#f1c40f'),
            ('Carga Diaria (kWh)', 'carga', '#ff6b35'),
            ('Descarga Diaria (kWh)', 'descarga', '#e74c3c')
        ]
        
        row_idx = 2
        for label_text, prefix, color in filas:
            tk.Label(info_cuadro, text=label_text, font=self.fuentes['normal'],
                    fg=self.colores['texto'], bg=self.colores['frame_light'],
                    anchor='w', padx=5).grid(row=row_idx, column=0, sticky="ew")
            
            for col, periodo in enumerate(['base', 'intermedio', 'punta', 'total'], 1):
                label = tk.Label(info_cuadro, text="0", font=self.fuentes['numeros'],
                               fg=color, bg=self.colores['frame_light'],
                               anchor='e', padx=5)
                label.grid(row=row_idx, column=col, sticky="ew")
                setattr(self, f"{prefix}_{periodo}", label)
            
            row_idx += 1
        
        tk.Frame(info_cuadro, height=2, bg=self.colores['frame']).grid(
            row=row_idx, column=0, columnspan=5, sticky="ew", pady=2)
        row_idx += 1
        
        tk.Label(info_cuadro, text="Arbitraje de Energía (MXN)",
                font=self.fuentes['normal'], fg=self.colores['texto_titulo'],
                bg=self.colores['frame_light'], anchor='w', padx=5).grid(
                row=row_idx, column=0, sticky="ew")
        
        for col, periodo in enumerate(['base', 'intermedio', 'punta', 'total'], 1):
            label = tk.Label(info_cuadro, text="$0", font=self.fuentes['numeros'],
                           fg=self.colores['exito'], bg=self.colores['frame_light'],
                           anchor='e', padx=5)
            label.grid(row=row_idx, column=col, sticky="ew")
            setattr(self, f'arbitraje_{periodo}', label)
    
    def actualizar_reloj(self):
        if not self.ventana_activa:
            return
        try:
            ahora = datetime.now().strftime("%H:%M:%S - %d/%m/%Y")
            if hasattr(self, 'status_bar'):
                self.status_bar.config(text=f"🕐 {ahora} | Sistema listo")
            if self.ventana_activa:
                self.timer_id = self.root.after(1000, self.actualizar_reloj)
        except:
            self.ventana_activa = False
    
    def actualizar_combo_fechas(self):
        if hasattr(self, 'combo_fecha') and self.ventana_activa:
            self.combo_fecha['values'] = dias_unicos_str
            if dias_unicos_str and not self.fecha_var.get():
                self.fecha_var.set(dias_unicos_str[0])
    
    def cambiar_medidor(self, medidor):
        if medidor == self.medidor_var.get():
            return
        
        if cargar_datos_medidor_dashboard(medidor):
            self.medidor_var.set(medidor)
            self.btn_ion.config(bg='#00d4ff' if medidor == 'ION' else '#2a3a4a')
            self.btn_banco.config(bg='#00d4ff' if medidor == 'BANCO' else '#2a3a4a')
            self.actualizar_combo_fechas()
            if dias_unicos_str:
                self.fecha_var.set(dias_unicos_str[0])
            self.root.title(f"Dashboard - Analisis de Energia BESS vs {medidor}")
            self.actualizar_todas_graficas()
            self.status_bar.config(text=f"Cambiado a medidor {medidor}")
    
    def filtrar_por_dia(self, fecha_str):
        if df_dashboard is None:
            return pd.DataFrame()
        
        fecha_dt = datetime.strptime(fecha_str, '%d/%m/%Y')
        inicio = fecha_dt.replace(hour=0, minute=0, second=0)
        fin = (fecha_dt + timedelta(days=1)).replace(hour=0, minute=0, second=0)
        
        mask = (df_dashboard['DATETIME'] >= inicio) & (df_dashboard['DATETIME'] < fin)
        datos_dia = df_dashboard[mask].copy()
        datos_dia = datos_dia.sort_values('DATETIME').reset_index(drop=True)
        
        if hasattr(self, 'label_registros'):
            self.label_registros.config(text=f"Registros: {len(datos_dia)} (cada 5 min)")
        
        return datos_dia
    
    def actualizar_cuadro_informacion(self):
        if not self.ventana_activa:
            return
        
        try:
            fecha_actual = self.fecha_var.get()
            if not fecha_actual:
                return
            
            mes_actual = datetime.strptime(fecha_actual, '%d/%m/%Y').month
            medidor = self.medidor_var.get()
            prefijo = 'ION' if medidor == 'ION' else 'BANCO'
            
            precio_base = self.tarifas.get('Base', {}).get(mes_actual, 0)
            precio_intermedio = self.tarifas.get('Intermedio', {}).get(mes_actual, 0)
            precio_punta = self.tarifas.get('Punta', {}).get(mes_actual, 0)
            
            ruta_acum = os.path.join(DIRECTORIO_REPORTES, f'ACUMULADOS_{prefijo}.csv')
            if os.path.exists(ruta_acum):
                df_acum = pd.read_csv(ruta_acum)
                fila_acum = df_acum[df_acum['FECHA'] == fecha_actual]
                
                if len(fila_acum) > 0:
                    fila = fila_acum.iloc[0]
                    consumo_base = int(round(fila.get('BASE_REC_ACUM', 0)))
                    consumo_intermedio = int(round(fila.get('INTERMEDIO_REC_ACUM', 0)))
                    consumo_punta = int(round(fila.get('PUNTA_REC_ACUM', 0)))
                    consumo_total = consumo_base + consumo_intermedio + consumo_punta
                    
                    demanda_base = int(np.ceil(fila.get('BASE_DEM_CON_BESS_MAX', 0)))
                    demanda_intermedio = int(np.ceil(fila.get('INTERMEDIO_DEM_CON_BESS_MAX', 0)))
                    demanda_punta = int(np.ceil(fila.get('PUNTA_DEM_CON_BESS_MAX', 0)))
                    
                    self.consumo_base.config(text=f"{consumo_base:,}")
                    self.consumo_intermedio.config(text=f"{consumo_intermedio:,}")
                    self.consumo_punta.config(text=f"{consumo_punta:,}")
                    self.consumo_total.config(text=f"{consumo_total:,}")
                    
                    self.demanda_base.config(text=f"{demanda_base:,}")
                    self.demanda_intermedio.config(text=f"{demanda_intermedio:,}")
                    self.demanda_punta.config(text=f"{demanda_punta:,}")
                    self.demanda_total.config(text=f"{demanda_punta:,}")
            
            ruta_bess_dia = os.path.join(DIRECTORIO_REPORTES, 'ENERGIA_BESS_POR_DIA.csv')
            if os.path.exists(ruta_bess_dia):
                df_bess_dia = pd.read_csv(ruta_bess_dia)
                fila_bess = df_bess_dia[df_bess_dia['FECHA'].str.strip() == fecha_actual.strip()]
                
                if len(fila_bess) > 0:
                    fila = fila_bess.iloc[0]
                    carga_base = int(round(fila.get('BASE_REC', 0)))
                    carga_intermedio = int(round(fila.get('INTERMEDIO_REC', 0)))
                    carga_punta = int(round(fila.get('PUNTA_REC', 0)))
                    carga_total = carga_base + carga_intermedio + carga_punta
                    
                    descarga_base = int(round(fila.get('BASE_ENT', 0)))
                    descarga_intermedio = int(round(fila.get('INTERMEDIO_ENT', 0)))
                    descarga_punta = int(round(fila.get('PUNTA_ENT', 0)))
                    descarga_total = descarga_base + descarga_intermedio + descarga_punta
                    
                    self.carga_base.config(text=f"{carga_base:,}")
                    self.carga_intermedio.config(text=f"{carga_intermedio:,}")
                    self.carga_punta.config(text=f"{carga_punta:,}")
                    self.carga_total.config(text=f"{carga_total:,}")
                    
                    self.descarga_base.config(text=f"{descarga_base:,}")
                    self.descarga_intermedio.config(text=f"{descarga_intermedio:,}")
                    self.descarga_punta.config(text=f"{descarga_punta:,}")
                    self.descarga_total.config(text=f"{descarga_total:,}")
                    
                    arbitraje_base = (descarga_base * precio_base) - (carga_base * precio_base)
                    arbitraje_intermedio = (descarga_intermedio * precio_intermedio) - (carga_intermedio * precio_intermedio)
                    arbitraje_punta = (descarga_punta * precio_punta) - (carga_punta * precio_punta)
                    arbitraje_total = arbitraje_base + arbitraje_intermedio + arbitraje_punta
                    
                    color_arbitraje = self.colores['exito'] if arbitraje_total >= 0 else self.colores['peligro']
                    self.arbitraje_base.config(text=f"${arbitraje_base:,.0f}")
                    self.arbitraje_intermedio.config(text=f"${arbitraje_intermedio:,.0f}")
                    self.arbitraje_punta.config(text=f"${arbitraje_punta:,.0f}")
                    self.arbitraje_total.config(text=f"${arbitraje_total:,.0f}", fg=color_arbitraje)
        except Exception as e:
            print(f"Error al actualizar cuadro de informacion: {e}")
    
    def graficar_comparacion_iusa(self, datos_dia):
        if not self.ventana_activa or datos_dia.empty:
            return
        
        self.ax_individual.clear()
        self.ax_individual.set_facecolor(self.colores['grafica'])
        
        fecha = self.fecha_var.get()
        medidor = self.medidor_var.get()
        prefijo = 'ION' if medidor == 'ION' else 'BANCO'
        
        col_iusa_con = f'IUSA_CON_BESS_{prefijo}_kW'
        col_iusa_sin = f'IUSA_SIN_BESS_{prefijo}_kW'
        
        if col_iusa_con not in datos_dia.columns or col_iusa_sin not in datos_dia.columns:
            self.ax_individual.text(0.5, 0.5, 'Datos no disponibles', 
                                   transform=self.ax_individual.transAxes,
                                   ha='center', va='center', color='white', fontsize=14)
            self.fig_individual.tight_layout()
            self.canvas_individual.draw()
            return
        
        iusa_con = datos_dia[col_iusa_con].values
        iusa_sin = datos_dia[col_iusa_sin].values
        horas = [dt.strftime('%H:%M') for dt in datos_dia['DATETIME']]
        
        color_con = '#00d4ff'
        color_sin = '#f1c40f'
        
        self.ax_individual.fill_between(range(len(horas)), 0, iusa_con, alpha=0.2, color=color_con)
        self.ax_individual.fill_between(range(len(horas)), 0, iusa_sin, alpha=0.15, color=color_sin)
        
        self.ax_individual.plot(range(len(horas)), iusa_con, marker='o', linewidth=2.5,
                              markersize=3, color=color_con, label=f'IUSA CON BESS ({prefijo})')
        self.ax_individual.plot(range(len(horas)), iusa_sin, marker='s', linewidth=2,
                              markersize=3, color=color_sin, label=f'IUSA SIN BESS ({prefijo})',
                              linestyle='--')
        
        self.ax_individual.set_title(f'Comparación IUSA - {prefijo}', fontsize=13,
                                    fontweight='bold', color='white')
        self.ax_individual.set_xlabel('Hora del día', fontsize=11, color='white')
        self.ax_individual.set_ylabel('Potencia (kW)', fontsize=11, color='white')
        self.ax_individual.tick_params(colors='white', rotation=45, labelsize=9)
        self.ax_individual.grid(True, alpha=0.15, color='white', linestyle='-')
        
        step = max(1, len(horas) // 12)
        xticks_pos = range(0, len(horas), step)
        xticks_labels = [horas[i] for i in xticks_pos]
        self.ax_individual.set_xticks(xticks_pos)
        self.ax_individual.set_xticklabels(xticks_labels, rotation=45, ha='right')
        self.ax_individual.set_xlim(-0.5, len(horas) - 0.5)
        self.ax_individual.axhline(y=0, color='white', linestyle='--', alpha=0.3)
        
        self.ax_individual.legend(loc='upper right', facecolor=self.colores['grafica'],
                                edgecolor='white', labelcolor='white', fontsize=9)
        
        for spine in self.ax_individual.spines.values():
            spine.set_color('white')
            spine.set_alpha(0.3)
        
        self.fig_individual.tight_layout()
        self.canvas_individual.draw()
    
    def graficar_perfil_carga(self, datos_dia):
        if not self.ventana_activa or datos_dia.empty:
            return
        
        self.ax_perfil.clear()
        self.ax_perfil.set_facecolor(self.colores['grafica'])
        
        fecha = self.fecha_var.get()
        medidor = self.medidor_var.get()
        prefijo = 'ION' if medidor == 'ION' else 'BANCO'
        
        col_medidor_rec = f'{prefijo}_REC_kW'
        col_bess_rec = 'BESS_REC_kW'
        col_bess_ent = 'BESS_ENT_kW'
        
        if col_medidor_rec not in datos_dia.columns or col_bess_rec not in datos_dia.columns:
            self.ax_perfil.text(0.5, 0.5, 'Datos no disponibles',
                              transform=self.ax_perfil.transAxes,
                              ha='center', va='center', color='white', fontsize=14)
            self.fig_perfil.tight_layout()
            self.canvas_perfil.draw()
            return
        
        medidor_rec = datos_dia[col_medidor_rec].values
        bess_rec = datos_dia[col_bess_rec].values
        bess_ent = -datos_dia[col_bess_ent].values if col_bess_ent in datos_dia.columns else np.zeros_like(bess_rec)
        horas = [dt.strftime('%H:%M') for dt in datos_dia['DATETIME']]
        
        self.ax_perfil.plot(range(len(horas)), medidor_rec, marker='o', linewidth=2,
                          markersize=3, color=self.colores['linea1'],
                          label=f'IUSA 1 - Con BESS')
        self.ax_perfil.plot(range(len(horas)), bess_rec, marker='s', linewidth=2,
                          markersize=3, color=self.colores['linea2'],
                          label='Carga BESS')
        self.ax_perfil.plot(range(len(horas)), bess_ent, marker='^', linewidth=2,
                          markersize=3, color=self.colores['linea3'],
                          label='Descarga BESS')
        
        self.ax_perfil.set_title(f'Perfil de Carga - {fecha}', fontsize=14,
                               fontweight='bold', color='white')
        self.ax_perfil.set_xlabel('Hora del día', fontsize=11, color='white')
        self.ax_perfil.set_ylabel('Potencia (kW)', fontsize=11, color='white')
        self.ax_perfil.tick_params(colors='white', rotation=45, labelsize=9)
        self.ax_perfil.grid(True, alpha=0.15, color='white', linestyle='-')
        
        step = max(1, len(horas) // 12)
        xticks_pos = range(0, len(horas), step)
        xticks_labels = [horas[i] for i in xticks_pos]
        self.ax_perfil.set_xticks(xticks_pos)
        self.ax_perfil.set_xticklabels(xticks_labels, rotation=45, ha='right')
        self.ax_perfil.set_xlim(-0.5, len(horas) - 0.5)
        self.ax_perfil.axhline(y=0, color='white', linestyle='--', alpha=0.3)
        
        self.ax_perfil.legend(loc='upper right', facecolor=self.colores['grafica'],
                            edgecolor='white', labelcolor='white', fontsize=9)
        
        for spine in self.ax_perfil.spines.values():
            spine.set_color('white')
            spine.set_alpha(0.3)
        
        self.fig_perfil.tight_layout()
        self.canvas_perfil.draw()
    
    def actualizar_todas_graficas(self):
        if not self.ventana_activa:
            return
        
        try:
            fecha_seleccionada = self.fecha_var.get()
            if not fecha_seleccionada:
                return
            
            self.status_bar.config(text=f"Cargando datos para {fecha_seleccionada}...")
            self.root.update()
            
            datos_dia = self.filtrar_por_dia(fecha_seleccionada)
            
            if datos_dia.empty:
                messagebox.showwarning("Sin datos", f"No hay datos para la fecha {fecha_seleccionada}")
                return
            
            self.actualizar_cuadro_informacion()
            self.graficar_comparacion_iusa(datos_dia)
            self.graficar_perfil_carga(datos_dia)
            
            self.status_bar.config(text=f"Gráficas actualizadas - {fecha_seleccionada}")
        except Exception as e:
            if self.ventana_activa:
                messagebox.showerror("Error", f"Error al actualizar gráficas: {str(e)}")
                self.status_bar.config(text=f"Error: {str(e)}")
    
    def generar_reporte_pdf(self):
        try:
            medidor = self.medidor_var.get()
            fecha = self.fecha_var.get()
            
            if not fecha:
                messagebox.showwarning("Advertencia", "No hay fecha seleccionada.")
                return
            
            self.btn_reporte.config(state='disabled', text='⏳ GENERANDO...')
            self.status_bar.config(text="Generando reporte PDF...")
            self.root.update()
            
            if generar_reporte_pdf(fecha, medidor):
                self.status_bar.config(text=f"Reporte generado exitosamente para {fecha}")
                messagebox.showinfo("Exito", 
                    f"✅ Reporte generado exitosamente\n"
                    f"Medidor: {medidor}\n"
                    f"Fecha: {fecha}\n\n"
                    f"Archivo: Reporte_{medidor}_{fecha.replace('/', '')}.pdf\n"
                    f"Ubicacion: {DIRECTORIO_REPORTES_DIARIOS}")
            else:
                messagebox.showerror("Error", "Error al generar el reporte")
            
            self.btn_reporte.config(state='normal', text='📄 GENERAR REPORTE PDF')
        except Exception as e:
            self.btn_reporte.config(state='normal', text='📄 GENERAR REPORTE PDF')
            messagebox.showerror("Error", f"Error al generar reporte: {str(e)}")

# ========== FUNCIÓN PRINCIPAL ==========

def main():
    """Función principal que ejecuta todo el flujo"""
    print("\n" + "=" * 70)
    print(" 🚀 BESS - SISTEMA UNIFICADO")
    print(" Procesamiento completo de datos y dashboard")
    print("=" * 70)
    
    # Paso 1: Verificar datos fuente
    print("\n📋 PASO 1: VERIFICANDO DATOS FUENTE")
    if not verificar_datos_fuente():
        print("\n❌ Error en la verificación de datos fuente")
        print("   Asegúrate de que los archivos estén en la carpeta ArchivosFuente")
        input("\nPresiona Enter para salir...")
        return
    
    # Paso 2: Filtrar datos
    print("\n📋 PASO 2: FILTRANDO DATOS")
    if not filtrar_datos():
        print("\n❌ Error en el filtrado de datos")
        input("\nPresiona Enter para salir...")
        return
    
    # Paso 3: Generar reportes BESS
    print("\n📋 PASO 3: GENERANDO REPORTES BESS")
    if not reporte_bess():
        print("\n❌ Error en la generación de reportes")
        input("\nPresiona Enter para salir...")
        return
    
    # Paso 4: Cargar datos para el dashboard
    print("\n📋 PASO 4: INICIANDO DASHBOARD")
    if cargar_datos_medidor_dashboard('ION'):
        print("✅ Datos cargados correctamente")
        print("   Iniciando dashboard...")
        root = tk.Tk()
        app = DashboardGraficas(root)
        root.mainloop()
    elif cargar_datos_medidor_dashboard('BANCO'):
        print("✅ Datos cargados correctamente (BANCO)")
        print("   Iniciando dashboard...")
        root = tk.Tk()
        app = DashboardGraficas(root)
        root.mainloop()
    else:
        print("❌ Error: No se pudieron cargar datos para el dashboard")
        input("\nPresiona Enter para salir...")
        return
    
    print("\n" + "=" * 70)
    print(" 🎯 PROCESO COMPLETADO")
    print("=" * 70)

if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\n\n⚠️ Proceso interrumpido por el usuario")
    except Exception as e:
        print(f"\n❌ Error inesperado: {e}")
        import traceback
        traceback.print_exc()
    
    print("\nPresiona Enter para salir...")
    try:
        input()
    except:
        pass