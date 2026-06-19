# bess_core.py
"""
BESS - Núcleo de Procesamiento de Datos
Contiene todas las funciones de procesamiento para el sistema BESS
"""

import pandas as pd
import numpy as np
import os
from datetime import datetime, timedelta
import warnings
import shutil

warnings.filterwarnings('ignore')

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

# ========== FUNCIONES DE UTILIDAD ==========

def crear_barra(progreso, longitud):
    """Crea una barra de progreso para mostrar el avance"""
    barra_llena = int(longitud * (progreso / 100))
    barra = '[' + '#' * barra_llena + ' ' * (longitud - barra_llena) + ']'
    return barra

def normalizar_fecha(fecha):
    """Convierte fecha al formato DD/MM/YYYY HH:MM"""
    if isinstance(fecha, str):
        return fecha
    return fecha.strftime('%d/%m/%Y %H:%M')

# ========== FUNCIONES DE TEMPORADA Y PERIODO ==========

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

# ========== FUNCIONES DE LECTURA DE ARCHIVOS ==========

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

# ========== FUNCIONES DE PROCESAMIENTO ==========

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

def generar_archivo_limpio(df, ruta_salida):
    """Genera un archivo CSV limpio"""
    df_limpio = df[['Fecha', 'KWH_REC', 'KWH_ENT']].copy()
    df_limpio['Fecha'] = df_limpio['Fecha'].apply(normalizar_fecha)
    df_limpio.to_csv(ruta_salida, index=False, encoding='utf-8-sig')
    print(f"✅ Archivo generado: {ruta_salida} ({len(df_limpio)} registros)")
    return df_limpio

def limpiar_archivos_fuente():
    """
    Elimina todos los archivos CSV del directorio ArchivosFuente
    después de que los datos han sido procesados.
    """
    archivos_eliminados = []
    errores = []
    
    if not os.path.exists(DIRECTORIO_FUENTE):
        return [], ["El directorio de archivos fuente no existe"]
    
    for archivo in os.listdir(DIRECTORIO_FUENTE):
        if archivo.lower().endswith('.csv'):
            ruta_archivo = os.path.join(DIRECTORIO_FUENTE, archivo)
            try:
                os.remove(ruta_archivo)
                archivos_eliminados.append(archivo)
                print(f"🗑️ Archivo fuente eliminado: {archivo}")
            except Exception as e:
                errores.append(f"Error al eliminar {archivo}: {str(e)}")
    
    return archivos_eliminados, errores

def filtrar_datos():
    """Función principal de filtrado de datos"""
    print("=" * 70)
    print("📊 PREPROCESADOR DE DATOS")
    print("=" * 70)
    print(f"📁 Carpeta de trabajo: {DIRECTORIO_PROCESADOS}")
    print("=" * 70)
    
    if not os.path.exists(DIRECTORIO_PROCESADOS):
        print(f"❌ Error: No existe la carpeta {DIRECTORIO_PROCESADOS}")
        return False, f"No existe la carpeta {DIRECTORIO_PROCESADOS}"
    
    archivos = {
        'BESS.csv': 'BESS_Filtrado.csv',
        'ION.csv': 'ION_Filtrado.csv',
        'Banco1.csv': 'Banco1_Filtrado.csv'
    }
    
    dfs = {}
    
    for archivo_origen, archivo_destino in archivos.items():
        ruta_origen = os.path.join(DIRECTORIO_PROCESADOS, archivo_origen)
        ruta_destino = os.path.join(DIRECTORIO_PROCESADOS, archivo_destino)
        
        if not os.path.exists(ruta_origen):
            return False, f"No se puede continuar sin el archivo {archivo_origen}"
        
        intercambiar = (archivo_origen == 'Banco1.csv')
        df = leer_archivo_perfil(ruta_origen, archivo_origen, intercambiar)
        if df is None:
            return False, f"Error al leer {archivo_origen}"
        
        dfs[archivo_origen] = df
    
    # Encontrar fechas comunes
    fechas_bess = set(dfs['BESS.csv']['Fecha'])
    fechas_ion = set(dfs['ION.csv']['Fecha'])
    fechas_banco = set(dfs['Banco1.csv']['Fecha'])
    
    fechas_comunes = fechas_bess.intersection(fechas_ion).intersection(fechas_banco)
    
    print(f"\n📊 Coincidencias (los 3): {len(fechas_comunes)} registros")
    
    if len(fechas_comunes) == 0:
        return False, "No se encontraron fechas coincidentes"
    
    # Filtrar y guardar
    for archivo_origen, archivo_destino in archivos.items():
        df_filtrado = dfs[archivo_origen][dfs[archivo_origen]['Fecha'].isin(fechas_comunes)].copy()
        df_filtrado = df_filtrado.sort_values('Fecha').reset_index(drop=True)
        ruta_destino = os.path.join(DIRECTORIO_PROCESADOS, archivo_destino)
        generar_archivo_limpio(df_filtrado, ruta_destino)
    
    # --- LIMPIAR ARCHIVOS FUENTE DESPUÉS DE PROCESAR ---
    print("\n" + "=" * 70)
    print("🗑️ LIMPIANDO ARCHIVOS FUENTE")
    print("=" * 70)
    archivos_eliminados, errores = limpiar_archivos_fuente()
    
    if archivos_eliminados:
        print(f"✅ {len(archivos_eliminados)} archivos fuente eliminados:")
        for archivo in archivos_eliminados:
            print(f"   - {archivo}")
    else:
        print("ℹ️ No había archivos fuente para eliminar")
    
    if errores:
        for error in errores:
            print(f"⚠️ {error}")
    
    print("\n" + "=" * 70)
    print("✅ PREPROCESAMIENTO COMPLETADO EXITOSAMENTE")
    print("=" * 70)
    
    mensaje_eliminacion = f" - {len(archivos_eliminados)} archivos fuente eliminados"
    return True, f"Procesados {len(fechas_comunes)} registros comunes{mensaje_eliminacion}"

# ========== FUNCIONES DE GENERACIÓN DE REPORTES ==========

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
        return False, f"No se encuentra archivo BESS"
    
    if not os.path.exists(ruta_medidor):
        print(f"ERROR: No se encuentra el archivo {nombre_medidor}: {ruta_medidor}")
        return False, f"No se encuentra archivo {nombre_medidor}"
    
    print(f"\n--- LECTURA Y AGRUPACION POR HORA ({prefijo}) ---")
    df_bess_hora = leer_y_agrupar_por_hora(ruta_bess, f'BESS_{prefijo}')
    df_medidor_hora = leer_y_agrupar_por_hora(ruta_medidor, nombre_medidor)
    
    if len(df_bess_hora) == 0 or len(df_medidor_hora) == 0:
        return False, f"No se pudieron cargar datos validos para {prefijo}"
    
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
    return True, f"Grupo {prefijo} procesado exitosamente"

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
    
    resultado_ion, msg_ion = procesar_grupo(RUTA_BESS, RUTA_ION, 'ION', 'ION', generar_bess_general=True)
    resultado_banco, msg_banco = procesar_grupo(RUTA_BESS, RUTA_BANCO, 'BANCO', 'Banco1', generar_bess_general=False)
    
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
    
    return resultado_ion and resultado_banco, msg_ion, msg_banco