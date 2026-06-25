# bess_core.py
"""
BESS - Núcleo de Procesamiento de Datos
Contiene todas las funciones de procesamiento para el sistema BESS
"""

import pandas as pd
import numpy as np
import os
import sys
from datetime import datetime, timedelta
import warnings
import shutil
import io
from decimal import Decimal, ROUND_HALF_UP

warnings.filterwarnings('ignore')

def _configurar_salida_consola():
    """Evita UnicodeEncodeError en Windows (cp1252) al imprimir emojis en consola."""
    for name in ('stdout', 'stderr'):
        stream = getattr(sys, name, None)
        if stream is None:
            continue
        try:
            if hasattr(stream, 'reconfigure'):
                stream.reconfigure(encoding='utf-8', errors='replace')
        except (AttributeError, OSError, ValueError, TypeError):
            pass

_configurar_salida_consola()

# ========== CONFIGURACIÓN GLOBAL ==========
DIRECTORIO_BASE = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'data')
DIRECTORIO_FUENTE = os.path.join(DIRECTORIO_BASE, 'ArchivosFuente')
DIRECTORIO_PROCESADOS = os.path.join(DIRECTORIO_BASE, 'ArchivosProcesados')
DIRECTORIO_REPORTES = os.path.join(DIRECTORIO_BASE, 'ArchivosReporte')
DIRECTORIO_REPORTES_DIARIOS = os.path.join(DIRECTORIO_BASE, 'ReportesDiarios')
DIRECTORIO_TARIFAS = os.path.join(DIRECTORIO_BASE, 'Tarifas')

_COLUMNAS_KVARH = ('KVARH_Q1', 'KVARH_Q2', 'KVARH_Q3', 'KVARH_Q4')

def _columnas_kvarh(df):
    """Columnas de reactivos presentes en un DataFrame."""
    return [c for c in _COLUMNAS_KVARH if c in df.columns]

def _normalizar_columnas_kvarh(df):
    """Conserva precisión completa de kVArh por cuadrante."""
    for col in _columnas_kvarh(df):
        df[col] = pd.to_numeric(df[col], errors='coerce').fillna(0)
    return df

def _columnas_kvarh_prefijo(prefijo):
    """Cuadrantes de kVArh según medidor: ION=Q1; BANCO=Q1+Q4."""
    if prefijo == 'ION':
        return ('KVARH_Q1',)
    if prefijo == 'BANCO':
        return ('KVARH_Q1', 'KVARH_Q4')
    return _COLUMNAS_KVARH

def _kvarh_total(df, prefijo=None):
    """kVArh por fila según reglas del medidor (ION: Q1; BANCO: Q1+Q4)."""
    cols = (
        [c for c in _columnas_kvarh_prefijo(prefijo) if c in df.columns]
        if prefijo
        else _columnas_kvarh(df)
    )
    if not cols:
        return pd.Series(0.0, index=df.index)
    return df[cols].sum(axis=1)

# Crear directorios
for dir_path in [DIRECTORIO_BASE, DIRECTORIO_FUENTE, DIRECTORIO_PROCESADOS,
                 DIRECTORIO_REPORTES, DIRECTORIO_REPORTES_DIARIOS, DIRECTORIO_TARIFAS]:
    os.makedirs(dir_path, exist_ok=True)

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

def validar_y_convertir_fecha(fecha_str):
    """
    Valida el formato de la fecha y si no coincide con el esperado '%Y-%m-%d %H:%M:%S',
    lo convierte a ese formato.
    """
    if isinstance(fecha_str, datetime):
        return fecha_str.strftime('%Y-%m-%d %H:%M:%S')
    
    fecha_str = str(fecha_str).strip()
    
    formatos_posibles = [
        '%Y-%m-%d %H:%M:%S',
        '%d/%m/%Y %H:%M:%S',
        '%d/%m/%Y %I:%M:%S %p',
        '%d/%m/%Y %I:%M:%S.%f %p',
        '%d/%m/%Y %I:%M:%S.%f',
        '%d/%m/%Y %I:%M %p',
        '%Y/%m/%d %H:%M:%S',
        '%Y-%m-%dT%H:%M:%S',
        '%Y-%m-%d %H:%M:%S.%f',
        '%d-%m-%Y %H:%M:%S',
        '%m/%d/%Y %H:%M:%S',
    ]
    
    fecha_limpia = fecha_str
    fecha_limpia = fecha_limpia.replace('p. m.', 'PM').replace('a. m.', 'AM')
    fecha_limpia = fecha_limpia.replace('p. m', 'PM').replace('a. m', 'AM')
    fecha_limpia = fecha_limpia.replace('p.m.', 'PM').replace('a.m.', 'AM')
    fecha_limpia = fecha_limpia.replace('p.m', 'PM').replace('a.m', 'AM')
    
    for formato in formatos_posibles:
        try:
            fecha_obj = datetime.strptime(fecha_limpia, formato)
            return fecha_obj.strftime('%Y-%m-%d %H:%M:%S')
        except ValueError:
            continue
    
    try:
        fecha_obj = pd.to_datetime(fecha_str)
        return fecha_obj.strftime('%Y-%m-%d %H:%M:%S')
    except:
        print(f"ADVERTENCIA: No se pudo convertir la fecha: {fecha_str}")
        return fecha_str

def buscar_logo():
    """Busca el logo en diferentes directorios"""
    posibles_rutas = [
        os.path.join(DIRECTORIO_BASE, 'Logo IUSASOL.png'),
        os.path.join(DIRECTORIO_BASE, 'LogoIUSASOL.jpeg'),
        os.path.join(DIRECTORIO_BASE, 'LogoIUSASOL.jpg'),
        os.path.join(DIRECTORIO_BASE, 'logo.jpeg'),
        os.path.join(DIRECTORIO_BASE, 'logo.jpg'),
        os.path.join(DIRECTORIO_TARIFAS, 'LogoIUSASOL.jpeg'),
        os.path.join(DIRECTORIO_TARIFAS, 'LogoIUSASOL.jpg'),
        os.path.join(DIRECTORIO_REPORTES_DIARIOS, 'LogoIUSASOL.jpeg'),
        os.path.join(DIRECTORIO_REPORTES_DIARIOS, 'LogoIUSASOL.jpg'),
        'LogoIUSASOL.jpeg',
        'LogoIUSASOL.jpg',
        'logo.jpeg',
        'logo.jpg'
    ]
    for ruta in posibles_rutas:
        if os.path.exists(ruta):
            print(f"Logo encontrado: {ruta}")
            return ruta
    print("Logo no encontrado en ninguna ruta")
    return None

def formatear_fecha_espanol(fecha_dt):
    """Formatea una fecha en español"""
    meses = {1: 'Enero', 2: 'Febrero', 3: 'Marzo', 4: 'Abril', 5: 'Mayo', 6: 'Junio',
             7: 'Julio', 8: 'Agosto', 9: 'Septiembre', 10: 'Octubre', 11: 'Noviembre', 12: 'Diciembre'}
    dia = fecha_dt.day
    mes = meses.get(fecha_dt.month, '')
    ano = fecha_dt.year
    return f"{dia} de {mes} de {ano}"

_PERIODOS_ENERGIA_KEYS = ('base', 'intermedio', 'punta')
_COL_ENERGIA_CON = {
    'base': 'BASE_REC',
    'intermedio': 'INTERMEDIO_REC',
    'punta': 'PUNTA_REC',
}
_COL_ENERGIA_SIN = {
    'base': 'BASE_REC_SIN_BESS',
    'intermedio': 'INTERMEDIO_REC_SIN_BESS',
    'punta': 'PUNTA_REC_SIN_BESS',
}
_TARIFA_PERIODO = {'base': 'Base', 'intermedio': 'Intermedio', 'punta': 'Punta'}

def energia_diaria_tiene_sin_bess(prefijo):
    ruta = os.path.join(DIRECTORIO_REPORTES, f'ENERGIA_{prefijo}_POR_DIA.csv')
    if not os.path.exists(ruta):
        return False
    return 'BASE_REC_SIN_BESS' in pd.read_csv(ruta, nrows=0).columns

def _fila_por_fecha_csv(ruta, fecha_str):
    if not os.path.exists(ruta):
        return None
    df = pd.read_csv(ruta)
    fila = df[df['FECHA'] == fecha_str]
    return fila.iloc[0] if len(fila) > 0 else None

def _celdas_kwh_tabla(base, intermedio, punta):
    """kWh por periodo redondeados; total = suma de periodos redondeados."""
    b = kwh_para_calculo(base)
    i = kwh_para_calculo(intermedio)
    p = kwh_para_calculo(punta)
    t = b + i + p
    return f"{b:,}", f"{i:,}", f"{p:,}", f"{t:,}"

def calcular_costo_energia_dia(fecha_str, prefijo, con_bess=True, tarifas=None):
    """Costo de energía de un solo día: kWh redondeados × tarifa por periodo."""
    if tarifas is None:
        tarifas = cargar_tarifas()
    columnas = _COL_ENERGIA_CON if con_bess else _COL_ENERGIA_SIN
    ruta = os.path.join(DIRECTORIO_REPORTES, f'ENERGIA_{prefijo}_POR_DIA.csv')
    fila = _fila_por_fecha_csv(ruta, fecha_str)
    if fila is None:
        return None
    mes = datetime.strptime(fecha_str, '%d/%m/%Y').month
    por_periodo = {}
    for clave in _PERIODOS_ENERGIA_KEYS:
        col = columnas[clave]
        if col not in fila.index:
            return None
        kwh = kwh_para_calculo(_a_num(fila.get(col, 0)))
        precio = tarifas.get(_TARIFA_PERIODO[clave], {}).get(mes, 0)
        por_periodo[clave] = {
            'kwh': kwh,
            'precio': precio,
            'costo_mxn': redondear_mxn_energia(kwh * precio),
        }
    total_mxn = redondear_mxn_energia(sum(p['costo_mxn'] for p in por_periodo.values()))
    return {
        'por_periodo': por_periodo,
        'total_kwh': sum(p['kwh'] for p in por_periodo.values()),
        'total_mxn': total_mxn,
    }

def calcular_arbitraje_dia(fecha_str, prefijo, tarifas=None):
    """
    Arbitraje del día seleccionado.
    Preferencia: costo sin BESS − costo con BESS (misma regla que el dashboard).
    Respaldo: (descarga − carga) × tarifa desde ENERGIA_BESS_POR_DIA.csv.
    """
    if tarifas is None:
        tarifas = cargar_tarifas()
    mes = datetime.strptime(fecha_str, '%d/%m/%Y').month

    if energia_diaria_tiene_sin_bess(prefijo):
        res_con = calcular_costo_energia_dia(fecha_str, prefijo, con_bess=True, tarifas=tarifas)
        res_sin = calcular_costo_energia_dia(fecha_str, prefijo, con_bess=False, tarifas=tarifas)
        if res_con is not None and res_sin is not None:
            return {
                'base': res_sin['por_periodo']['base']['costo_mxn'] - res_con['por_periodo']['base']['costo_mxn'],
                'intermedio': res_sin['por_periodo']['intermedio']['costo_mxn'] - res_con['por_periodo']['intermedio']['costo_mxn'],
                'punta': res_sin['por_periodo']['punta']['costo_mxn'] - res_con['por_periodo']['punta']['costo_mxn'],
                'total': res_sin['total_mxn'] - res_con['total_mxn'],
            }

    fila = _fila_por_fecha_csv(
        os.path.join(DIRECTORIO_REPORTES, 'ENERGIA_BESS_POR_DIA.csv'), fecha_str
    )
    if fila is None:
        return {'base': 0.0, 'intermedio': 0.0, 'punta': 0.0, 'total': 0.0}

    carga_base = _a_num(fila.get('BASE_REC', 0))
    carga_intermedio = _a_num(fila.get('INTERMEDIO_REC', 0))
    carga_punta = _a_num(fila.get('PUNTA_REC', 0))
    descarga_base = _a_num(fila.get('BASE_ENT', 0))
    descarga_intermedio = _a_num(fila.get('INTERMEDIO_ENT', 0))
    descarga_punta = _a_num(fila.get('PUNTA_ENT', 0))

    precio_base = tarifas['Base'].get(mes, 0)
    precio_intermedio = tarifas['Intermedio'].get(mes, 0)
    precio_punta = tarifas['Punta'].get(mes, 0)

    arbitraje_base = redondear_mxn_energia(
        (kwh_para_calculo(descarga_base) - kwh_para_calculo(carga_base)) * precio_base
    )
    arbitraje_intermedio = redondear_mxn_energia(
        (kwh_para_calculo(descarga_intermedio) - kwh_para_calculo(carga_intermedio)) * precio_intermedio
    )
    arbitraje_punta = redondear_mxn_energia(
        (kwh_para_calculo(descarga_punta) - kwh_para_calculo(carga_punta)) * precio_punta
    )
    return {
        'base': arbitraje_base,
        'intermedio': arbitraje_intermedio,
        'punta': arbitraje_punta,
        'total': redondear_mxn_energia(arbitraje_base + arbitraje_intermedio + arbitraje_punta),
    }

def obtener_bess_energia_dia(fecha_str):
    """Carga y descarga BESS del día desde ENERGIA_BESS_POR_DIA.csv."""
    fila = _fila_por_fecha_csv(
        os.path.join(DIRECTORIO_REPORTES, 'ENERGIA_BESS_POR_DIA.csv'), fecha_str
    )
    if fila is None:
        return {
            'carga_base': 0.0, 'carga_intermedio': 0.0, 'carga_punta': 0.0,
            'descarga_base': 0.0, 'descarga_intermedio': 0.0, 'descarga_punta': 0.0,
        }
    return {
        'carga_base': _a_num(fila.get('BASE_REC', 0)),
        'carga_intermedio': _a_num(fila.get('INTERMEDIO_REC', 0)),
        'carga_punta': _a_num(fila.get('PUNTA_REC', 0)),
        'descarga_base': _a_num(fila.get('BASE_ENT', 0)),
        'descarga_intermedio': _a_num(fila.get('INTERMEDIO_ENT', 0)),
        'descarga_punta': _a_num(fila.get('PUNTA_ENT', 0)),
    }

def cargar_tarifas():
    """Carga las tarifas desde el archivo CSV"""
    ruta = os.path.join(DIRECTORIO_TARIFAS, 'Tarifas_2026.csv')
    if not os.path.exists(ruta):
        return {'Base': {i: 0 for i in range(1, 13)}, 'Intermedio': {i: 0 for i in range(1, 13)}, 'Punta': {i: 0 for i in range(1, 13)}}
    try:
        df = pd.read_csv(ruta)
        tarifas = {'Base': {}, 'Intermedio': {}, 'Punta': {}}
        for _, row in df.iterrows():
            tipo = row['Tarifa'].strip()
            if tipo in tarifas:
                for mes in range(1, 13):
                    tarifas[tipo][mes] = float(row.get(str(mes), 0))
        return tarifas
    except:
        return {'Base': {i: 0 for i in range(1, 13)}, 'Intermedio': {i: 0 for i in range(1, 13)}, 'Punta': {i: 0 for i in range(1, 13)}}

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

# ========== FUNCIONES DE IDENTIFICACIÓN Y RENOMBRADO ==========

def identificar_y_renombrar_archivos():
    """
    Identifica archivos en DIRECTORIO_FUENTE por patrones en el nombre
    y los renombra a los nombres estándar: ION.csv, BESS.csv, Banco1.csv
    """
    # Patrones de búsqueda para cada archivo
    patrones = {
        'ION': ['IUSA1', 'IUSA', 'ION'],
        'BESS': ['CS3878', 'BESS'],
        'Banco1': ['CS1996', 'BANCO1', 'Banco1']
    }
    
    renombrados = {}
    errores = []
    
    if not os.path.exists(DIRECTORIO_FUENTE):
        os.makedirs(DIRECTORIO_FUENTE, exist_ok=True)
        return {'renombrados': {}, 'errores': ['Directorio fuente no existe, se creó vacío']}
    
    archivos = os.listdir(DIRECTORIO_FUENTE)
    
    print("\n" + "=" * 70)
    print("🔍 IDENTIFICANDO ARCHIVOS POR PATRÓN")
    print("=" * 70)
    print(f"📁 Archivos encontrados en {DIRECTORIO_FUENTE}:")
    for a in archivos:
        print(f"   - {a}")
    print("=" * 70)
    
    for nombre_estandar, patrones_busqueda in patrones.items():
        archivo_encontrado = None
        
        for archivo in archivos:
            archivo_lower = archivo.lower()
            for patron in patrones_busqueda:
                if patron.lower() in archivo_lower:
                    archivo_encontrado = archivo
                    break
            if archivo_encontrado:
                break
        
        if archivo_encontrado:
            ruta_origen = os.path.join(DIRECTORIO_FUENTE, archivo_encontrado)
            nombre_destino = f'{nombre_estandar}.csv'
            ruta_destino = os.path.join(DIRECTORIO_FUENTE, nombre_destino)

            # Ya está con el nombre estándar (p. ej. ION.csv → ION.csv)
            if os.path.normcase(ruta_origen) == os.path.normcase(ruta_destino):
                renombrados[nombre_estandar] = {
                    'origen': archivo_encontrado,
                    'destino': nombre_destino,
                }
                print(f'✅ {archivo_encontrado} (nombre estándar, sin cambios)')
                continue

            try:
                # Si el archivo destino ya existe, hacer backup
                if os.path.exists(ruta_destino):
                    backup_path = ruta_destino.replace('.csv', '_backup.csv')
                    shutil.move(ruta_destino, backup_path)
                    print(f'💾 Backup creado: {os.path.basename(backup_path)}')

                os.rename(ruta_origen, ruta_destino)
                renombrados[nombre_estandar] = {
                    'origen': archivo_encontrado,
                    'destino': nombre_destino,
                }
                print(f'✅ {archivo_encontrado} → {nombre_destino}')
            except Exception as e:
                errores.append(f'Error al renombrar {archivo_encontrado}: {str(e)}')
        else:
            errores.append(f"⚠️ No se encontró archivo que coincida con los patrones de {nombre_estandar}")
    
    print("=" * 70)
    if renombrados:
        print("📋 Archivos renombrados:")
        for nombre, info in renombrados.items():
            print(f"   ✅ {info['origen']} → {info['destino']}")
    if errores:
        print("⚠️ Errores/Advertencias:")
        for error in errores:
            print(f"   {error}")
    print("=" * 70)
    
    return {'renombrados': renombrados, 'errores': errores}

# ========== FUNCIONES DE LECTURA DE ARCHIVOS ==========

def leer_archivo_perfil(ruta, nombre_archivo,intercambiar_columnas=False):
    """Lee un archivo de perfil completo"""
    try:
        df = pd.read_csv(ruta, encoding='utf-8-sig')
    except Exception as e:
        print(f"❌ Error al leer {nombre_archivo}: {e}")
        return None
    
    print(f"📁 {nombre_archivo}: {len(df)} registros")
    
    # Verificar columnas esperadas
    columnas_esperadas = ['Fecha', 'KWH_REC', 'KWH_ENT']
    for col in columnas_esperadas:
        if col not in df.columns:
            # Buscar columna por nombre alternativo
            for df_col in df.columns:
                if 'fecha' in df_col.lower() or 'date' in df_col.lower():
                    df = df.rename(columns={df_col: 'Fecha'})
                    break
            else:
                df = df.rename(columns={df.columns[0]: 'Fecha'})
            
            for df_col in df.columns:
                if 'rec' in df_col.lower() or 'kwh_r' in df_col.lower():
                    df = df.rename(columns={df_col: 'KWH_REC'})
                    break
            
            for df_col in df.columns:
                if 'ent' in df_col.lower() or 'kwh_e' in df_col.lower():
                    df = df.rename(columns={df_col: 'KWH_ENT'})
                    break
    
    # Convertir fechas
    df['Fecha'] = df['Fecha'].apply(validar_y_convertir_fecha)
    df['Fecha'] = pd.to_datetime(df['Fecha'], errors='coerce')
    
    registros_invalidos = df['Fecha'].isna().sum()
    if registros_invalidos > 0:
        print(f"⚠️ {nombre_archivo}: Se eliminaron {registros_invalidos} registros con fecha inválida")
        df = df.dropna(subset=['Fecha'])
    
    df['KWH_REC'] = pd.to_numeric(df['KWH_REC'], errors='coerce').fillna(0)
    df['KWH_ENT'] = pd.to_numeric(df['KWH_ENT'], errors='coerce').fillna(0)
    df = _normalizar_columnas_kvarh(df)
    
    if intercambiar_columnas:
        print(f"🔄 {nombre_archivo}: Intercambiando KWH_REC ↔ KWH_ENT")
        temp_rec = df['KWH_REC'].copy()
        df['KWH_REC'] = df['KWH_ENT']
        df['KWH_ENT'] = temp_rec
    
    print(f"✅ {nombre_archivo}: {len(df)} registros válidos")
    return df

def leer_sin_agrupar(ruta_archivo):
    """Lee el archivo original SIN agrupar (incluye kVArh si existen)."""
    df = pd.read_csv(ruta_archivo, encoding='utf-8-sig')
    columna_fecha = df.columns[0]
    df['DATETIME'] = pd.to_datetime(df[columna_fecha], format='%d/%m/%Y %H:%M', errors='coerce')
    if df['DATETIME'].isna().all():
        df['DATETIME'] = pd.to_datetime(df[columna_fecha], errors='coerce')
    df = df.dropna(subset=['DATETIME']).reset_index(drop=True)

    if 'KWH_REC' in df.columns and 'KWH_ENT' in df.columns:
        df['KWH_REC'] = pd.to_numeric(df['KWH_REC'], errors='coerce').fillna(0)
        df['KWH_ENT'] = pd.to_numeric(df['KWH_ENT'], errors='coerce').fillna(0)
    else:
        col_kwh_rec = df.columns[1]
        col_kwh_ent = df.columns[2]
        df['KWH_REC'] = pd.to_numeric(df[col_kwh_rec], errors='coerce').fillna(0)
        df['KWH_ENT'] = pd.to_numeric(df[col_kwh_ent], errors='coerce').fillna(0)

    df = _normalizar_columnas_kvarh(df)
    df['FECHA_HORA'] = df['DATETIME'].dt.strftime('%d/%m/%Y %H:%M')

    columnas = ['FECHA_HORA', 'KWH_REC', 'KWH_ENT'] + _columnas_kvarh(df)
    return df[columnas]

def leer_y_agrupar_por_hora(ruta_archivo, nombre_archivo):
    """Lee y agrupa datos por hora (incluye kVArh si existen)."""
    df = pd.read_csv(ruta_archivo, encoding='utf-8-sig')
    columna_fecha = df.columns[0]
    df['DATETIME'] = pd.to_datetime(df[columna_fecha], format='%d/%m/%Y %H:%M', errors='coerce')
    if df['DATETIME'].isna().all():
        df['DATETIME'] = pd.to_datetime(df[columna_fecha], errors='coerce')
    df = df.dropna(subset=['DATETIME']).reset_index(drop=True)

    if 'KWH_REC' in df.columns and 'KWH_ENT' in df.columns:
        df['KWH_REC'] = pd.to_numeric(df['KWH_REC'], errors='coerce').fillna(0)
        df['KWH_ENT'] = pd.to_numeric(df['KWH_ENT'], errors='coerce').fillna(0)
    else:
        col_kwh_rec = df.columns[1]
        col_kwh_ent = df.columns[2]
        df['KWH_REC'] = pd.to_numeric(df[col_kwh_rec], errors='coerce').fillna(0)
        df['KWH_ENT'] = pd.to_numeric(df[col_kwh_ent], errors='coerce').fillna(0)

    df = _normalizar_columnas_kvarh(df)
    df = df.sort_values('DATETIME').reset_index(drop=True)
    num_registros = len(df)
    num_horas = num_registros // 12

    if num_registros % 12 != 0:
        print(f"  - ADVERTENCIA: {num_registros % 12} registros sobrantes en {nombre_archivo}")
        df = df.iloc[:num_horas * 12].reset_index(drop=True)

    df['GRUPO'] = np.arange(len(df)) // 12

    agg = {'DATETIME': 'first', 'KWH_REC': 'sum', 'KWH_ENT': 'sum'}
    for col in _columnas_kvarh(df):
        agg[col] = 'sum'

    df_agrupado = df.groupby('GRUPO').agg(agg).reset_index(drop=True)

    df_agrupado['HORA'] = df_agrupado['DATETIME'].dt.hour + 1
    df_agrupado['HORA'] = df_agrupado['HORA'].replace(25, 1)
    df_agrupado['FECHA'] = df_agrupado['DATETIME'].dt.strftime('%d/%m/%Y')
    df_agrupado['FECHA_HORA'] = df_agrupado['DATETIME'].dt.strftime('%d/%m/%Y %H:%M')

    columnas = ['FECHA', 'HORA', 'FECHA_HORA', 'KWH_REC', 'KWH_ENT'] + _columnas_kvarh(df_agrupado)
    return df_agrupado[columnas]

# ========== FUNCIONES DE PROCESAMIENTO ==========

def procesar_archivo_verificacion(ruta_origen, ruta_destino, nombre_archivo, intercambiar=False):
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
        perfil = leer_archivo_perfil(ruta_completa_origen, nombre_archivo)
        if perfil is None:
            return False
        
        print(f"📁 Archivo original: {nombre_archivo}")
        print(f"📏 Registros originales: {len(perfil)}")
        
        # Eliminar duplicados
        perfil_sin_duplicados = perfil.drop_duplicates(subset=['Fecha'], keep='first')
        renglones_duplicados = len(perfil) - len(perfil_sin_duplicados)
        print(f"🗑️ Renglones duplicados eliminados: {renglones_duplicados}")
        
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
        
        perfil_completo = perfil_completo.sort_values(by='Fecha', ascending=True).reset_index(drop=True)
        
        os.makedirs(ruta_destino, exist_ok=True)
        ruta_guardado = os.path.join(ruta_destino, nombre_archivo)
        
        if os.path.exists(ruta_guardado):
            backup_path = ruta_guardado.replace('.csv', '_backup.csv')
            shutil.copy2(ruta_guardado, backup_path)
            print(f"💾 Backup creado: {os.path.basename(backup_path)}")
        
        # Guardar con formato de fecha estandarizado
        perfil_completo['Fecha'] = perfil_completo['Fecha'].dt.strftime('%Y-%m-%d %H:%M:%S')
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
    """Función principal de verificación de datos fuente. Retorna (éxito, mensaje)."""
    
    # PASO 1: Identificar y renombrar archivos
    identificar_y_renombrar_archivos()
    
    # PASO 2: Procesar archivos estándar
    archivos = ['Banco1.csv', 'BESS.csv', 'ION.csv']
    
    print("\n" + "="*70)
    print("🔍 VERIFICADOR DE PERFILES DE CARGA")
    print("="*70)
    print(f"📁 Carpeta origen: {DIRECTORIO_FUENTE}")
    print(f"📁 Carpeta destino: {DIRECTORIO_PROCESADOS}")
    print("="*70)
    
    if not os.path.exists(DIRECTORIO_FUENTE):
        print(f"❌ Error: No existe la carpeta {DIRECTORIO_FUENTE}")
        os.makedirs(DIRECTORIO_FUENTE, exist_ok=True)
        print(f"✅ Carpeta creada: {DIRECTORIO_FUENTE}")
        return False, f"No existía la carpeta {DIRECTORIO_FUENTE}. Coloque ION.csv, BESS.csv y Banco1.csv ahí."
    
    archivos_encontrados = []
    for archivo in archivos:
        ruta_completa = os.path.join(DIRECTORIO_FUENTE, archivo)
        if os.path.exists(ruta_completa):
            archivos_encontrados.append(archivo)
    
    if not archivos_encontrados:
        print(f"❌ No se encontraron archivos en {DIRECTORIO_FUENTE}")
        return False, (
            "No se encontraron archivos en ArchivosFuente. "
            "Copie ION.csv, BESS.csv y Banco1.csv en data/ArchivosFuente."
        )
    
    print(f"\n📋 Archivos encontrados: {', '.join(archivos_encontrados)}")
    
    resultados = {}
    for archivo in archivos:
        if os.path.exists(os.path.join(DIRECTORIO_FUENTE, archivo)):
            intercambiar = (archivo == 'Banco1.csv')
            resultados[archivo] = procesar_archivo_verificacion(
                DIRECTORIO_FUENTE, DIRECTORIO_PROCESADOS, archivo, intercambiar
            )
        else:
            print(f"\n⚠️ Archivo no encontrado: {archivo} (omitido)")
            resultados[archivo] = False
    
    print("\n" + "="*70)
    print("📊 RESUMEN FINAL VERIFICACIÓN")
    print("="*70)
    for archivo, exito in resultados.items():
        estado = "✅ Éxito" if exito else "❌ Falló"
        print(f"   {archivo}: {estado}")
    
    if all(resultados.values()):
        return True, "Verificación completada para ION, BESS y Banco1."

    faltantes = [a for a in archivos if not os.path.exists(os.path.join(DIRECTORIO_FUENTE, a))]
    fallidos = [a for a, ok in resultados.items() if not ok]
    partes = []
    if faltantes:
        partes.append(f"faltan en fuente: {', '.join(faltantes)}")
    if fallidos:
        partes.append(f"error al procesar: {', '.join(fallidos)}")
    detalle = '; '.join(partes)
    return False, (
        f"Verificación incompleta ({detalle}). "
        "Cierre Excel u otros programas que tengan abiertos los CSV en ArchivosProcesados."
    )

def generar_archivo_limpio(df, ruta_salida):
    """Genera un archivo CSV limpio (conserva kVArh por cuadrante si existen)."""
    columnas = ['Fecha', 'KWH_REC', 'KWH_ENT'] + _columnas_kvarh(df)
    df_limpio = df[columnas].copy()
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
    """
    Función principal de filtrado de datos.
    Lee los archivos procesados, encuentra fechas comunes entre los 3 archivos
    y genera archivos filtrados con solo los registros coincidentes.
    """
    print("=" * 70)
    print("📊 PREPROCESADOR DE DATOS - FILTRADO POR FECHAS COMUNES")
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
    
    # Leer archivos
    for archivo_origen, archivo_destino in archivos.items():
        ruta_origen = os.path.join(DIRECTORIO_PROCESADOS, archivo_origen)
        ruta_destino = os.path.join(DIRECTORIO_PROCESADOS, archivo_destino)
        
        if not os.path.exists(ruta_origen):
            return False, f"No se puede continuar sin el archivo {archivo_origen}"
        
        intercambiar = (archivo_origen == 'Banco1.csv')
        df = leer_archivo_perfil(ruta_origen, archivo_origen,intercambiar)
        if df is None:
            return False, f"Error al leer {archivo_origen}"
        
        dfs[archivo_origen] = df
    
    # Encontrar fechas comunes entre los 3 archivos
    print("\n" + "="*70)
    print("🔍 ENCONTRANDO FECHAS COMUNES ENTRE LOS 3 ARCHIVOS")
    print("="*70)
    
    fechas_bess = set(dfs['BESS.csv']['Fecha'])
    fechas_ion = set(dfs['ION.csv']['Fecha'])
    fechas_banco = set(dfs['Banco1.csv']['Fecha'])
    
    print(f"📊 Registros BESS: {len(fechas_bess)}")
    print(f"📊 Registros ION: {len(fechas_ion)}")
    print(f"📊 Registros Banco1: {len(fechas_banco)}")
    
    fechas_comunes = fechas_bess.intersection(fechas_ion).intersection(fechas_banco)
    
    print(f"\n📊 Fechas comunes entre los 3 archivos: {len(fechas_comunes)}")
    
    if len(fechas_comunes) == 0:
        return False, "No se encontraron fechas coincidentes entre los 3 archivos"
    
    # Mostrar rango de fechas de cada archivo
    print("\n📅 Rangos de fechas:")
    for nombre, df in dfs.items():
        print(f"   {nombre}: {df['Fecha'].min()} a {df['Fecha'].max()} ({len(df)} registros)")
    
    # Filtrar y guardar solo las fechas comunes
    print("\n" + "="*70)
    print("📊 GENERANDO ARCHIVOS FILTRADOS")
    print("="*70)
    
    for archivo_origen, archivo_destino in archivos.items():
        df_filtrado = dfs[archivo_origen][dfs[archivo_origen]['Fecha'].isin(fechas_comunes)].copy()
        df_filtrado = df_filtrado.sort_values('Fecha').reset_index(drop=True)
        ruta_destino = os.path.join(DIRECTORIO_PROCESADOS, archivo_destino)
        generar_archivo_limpio(df_filtrado, ruta_destino)
    
    # Limpiar archivos fuente después de procesar
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
    print(f"📊 Archivos filtrados generados con {len(fechas_comunes)} registros coincidentes")
    
    mensaje_eliminacion = f" - {len(archivos_eliminados)} archivos fuente eliminados"
    return True, f"Procesados {len(fechas_comunes)} registros comunes entre los 3 archivos{mensaje_eliminacion}"

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
    
    col_con = f'IUSA_CON_BESS_{prefijo}_kW'
    columnas_export = [
        'FECHA_HORA',
        'KWH_REC_BESS', 'KWH_ENT_BESS',
        'BESS_REC_kW', 'BESS_ENT_kW',
        col_con,
        f'{col_con}_DEM_15min',
        f'IUSA_SIN_BESS_{prefijo}_kW_DEM_15min',
    ]
    
    nombre_archivo = f'COMBINADO_POR_MINUTO_{prefijo}.csv'
    ruta_salida = os.path.join(DIRECTORIO_REPORTES, nombre_archivo)
    df_combinado[columnas_export].to_csv(ruta_salida, index=False)
    
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
    ruta_comb_hora = os.path.join(DIRECTORIO_REPORTES, f'COMBINADO_POR_HORA_{prefijo}.csv')
    if 'FECHA_HORA' not in df_medidor_hora.columns and os.path.exists(ruta_comb_hora):
        df_comb_ref = pd.read_csv(ruta_comb_hora)[['FECHA_HORA']].sort_values('FECHA_HORA').reset_index(drop=True)
        df_med_ord = df_medidor_hora.sort_values(['FECHA', 'HORA']).reset_index(drop=True)
        if len(df_med_ord) == len(df_comb_ref):
            df_medidor_hora = df_med_ord
            df_medidor_hora['FECHA_HORA'] = df_comb_ref['FECHA_HORA']

    df_minuto = pd.read_csv(ruta_minuto)
    if 'PERIODO' not in df_minuto.columns:
        df_minuto['PERIODO'] = df_minuto['FECHA_HORA'].apply(obtener_periodo_por_fecha_hora)
    df_minuto['FECHA'] = pd.to_datetime(df_minuto['FECHA_HORA'], format='%d/%m/%Y %H:%M').dt.strftime('%d/%m/%Y')
    
    # Energías diarias del medidor
    df_med_ent = df_medidor_hora.groupby(['FECHA', 'PERIODO'])['KWH_ENT'].sum().reset_index()
    df_med_ent_pivot = df_med_ent.pivot_table(index='FECHA', columns='PERIODO', values='KWH_ENT', aggfunc='sum', fill_value=0).reset_index()
    df_med_ent_pivot = df_med_ent_pivot.rename(columns={'Base': 'BASE_ENT', 'Intermedio': 'INTERMEDIO_ENT', 'Punta': 'PUNTA_ENT'})
    
    df_med_rec = df_medidor_hora.groupby(['FECHA', 'PERIODO'])['KWH_REC'].sum().reset_index()
    df_med_rec_pivot = df_med_rec.pivot_table(index='FECHA', columns='PERIODO', values='KWH_REC', aggfunc='sum', fill_value=0).reset_index()
    df_med_rec_pivot = df_med_rec_pivot.rename(columns={'Base': 'BASE_REC', 'Intermedio': 'INTERMEDIO_REC', 'Punta': 'PUNTA_REC'})
    
    df_med_diario = df_med_ent_pivot.merge(df_med_rec_pivot, on='FECHA', how='outer').fillna(0)

    # Energía sin BESS: mismo FECHA/PERIODO que el medidor (ENERGIA_*_POR_HORA)
    col_rec = f'KWH_REC_{prefijo}'
    if (
        os.path.exists(ruta_comb_hora)
        and 'FECHA_HORA' in df_medidor_hora.columns
    ):
        df_comb_hora = pd.read_csv(ruta_comb_hora)
        if all(c in df_comb_hora.columns for c in [col_rec, 'KWH_REC_BESS', 'KWH_ENT_BESS', 'FECHA_HORA']):
            df_comb_hora['KWH_SIN_BESS'] = (
                pd.to_numeric(df_comb_hora[col_rec], errors='coerce').fillna(0)
                - pd.to_numeric(df_comb_hora['KWH_REC_BESS'], errors='coerce').fillna(0)
                + pd.to_numeric(df_comb_hora['KWH_ENT_BESS'], errors='coerce').fillna(0)
            )
            df_sin = df_comb_hora[['FECHA_HORA', 'KWH_SIN_BESS']].merge(
                df_medidor_hora[['FECHA_HORA', 'FECHA', 'PERIODO']],
                on='FECHA_HORA',
                how='inner',
            )
            df_sin_rec = df_sin.groupby(['FECHA', 'PERIODO'])['KWH_SIN_BESS'].sum().reset_index()
            df_sin_pivot = df_sin_rec.pivot_table(
                index='FECHA', columns='PERIODO', values='KWH_SIN_BESS', aggfunc='sum', fill_value=0
            ).reset_index()
            df_sin_pivot = df_sin_pivot.rename(columns={
                'Base': 'BASE_REC_SIN_BESS',
                'Intermedio': 'INTERMEDIO_REC_SIN_BESS',
                'Punta': 'PUNTA_REC_SIN_BESS',
            })
            df_med_diario = df_med_diario.merge(df_sin_pivot, on='FECHA', how='left').fillna(0)
        else:
            df_med_diario['BASE_REC_SIN_BESS'] = 0
            df_med_diario['INTERMEDIO_REC_SIN_BESS'] = 0
            df_med_diario['PUNTA_REC_SIN_BESS'] = 0
    else:
        df_med_diario['BASE_REC_SIN_BESS'] = 0
        df_med_diario['INTERMEDIO_REC_SIN_BESS'] = 0
        df_med_diario['PUNTA_REC_SIN_BESS'] = 0

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

    if _columnas_kvarh(df_medidor_hora):
        df_medidor_hora = _normalizar_columnas_kvarh(df_medidor_hora)
        df_medidor_hora['KVARH'] = _kvarh_total(df_medidor_hora, prefijo)
        df_kvarh_dia = df_medidor_hora.groupby('FECHA')['KVARH'].sum().reset_index()
        df_med_diario = df_med_diario.merge(df_kvarh_dia, on='FECHA', how='left')
        df_med_diario['KVARH'] = pd.to_numeric(df_med_diario['KVARH'], errors='coerce').fillna(0)
    else:
        df_med_diario['KVARH'] = 0.0
    
    columnas_med = ['FECHA', 'BASE_ENT', 'INTERMEDIO_ENT', 'PUNTA_ENT', 'BASE_REC', 'INTERMEDIO_REC', 'PUNTA_REC',
                    'BASE_REC_SIN_BESS', 'INTERMEDIO_REC_SIN_BESS', 'PUNTA_REC_SIN_BESS', 'KVARH',
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
    
    for col in ('BASE_REC', 'INTERMEDIO_REC', 'PUNTA_REC'):
        df_acum_med[f"{col}_ACUM"] = df_med_dia.groupby('MES')[col].cumsum()

    if 'KVARH' in df_med_dia.columns:
        df_acum_med['KVARH_ACUM'] = df_med_dia.groupby('MES')['KVARH'].cumsum()

    grupos_demanda = [
        ['BASE_DEM_CON_BESS', 'INTERMEDIO_DEM_CON_BESS', 'PUNTA_DEM_CON_BESS'],
        ['BASE_DEM_SIN_BESS', 'INTERMEDIO_DEM_SIN_BESS', 'PUNTA_DEM_SIN_BESS'],
    ]
    for cols_demanda in grupos_demanda:
        cols_fechahora = [f"{col}_FECHA_HORA" for col in cols_demanda]
        for col_valor, col_fh in zip(cols_demanda, cols_fechahora):
            max_valor = 0
            max_fh = ""
            mes_actual = None
            valores = []
            fechahoras = []

            for _, row in df_med_dia.iterrows():
                mes_row = row['MES']
                if mes_actual != mes_row:
                    max_valor = 0
                    max_fh = ""
                    mes_actual = mes_row

                valor_actual = row.get(col_valor, 0)
                fh_actual = row.get(col_fh, '')
                if pd.isna(valor_actual):
                    valor_actual = 0
                if pd.isna(fh_actual):
                    fh_actual = ''
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
    
    df_medidor_output = df_medidor_hora_con_periodo[
        ['FECHA', 'HORA', 'FECHA_HORA', 'KWH_REC', 'KWH_ENT', 'PERIODO']
        + _columnas_kvarh(df_medidor_hora_con_periodo)
    ].copy()
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

# ========== REPORTE PDF — ESTILOS Y HELPERS ==========
_PDF = {
    'primary': '#1a5276',
    'secondary': '#2e86c1',
    'base': '#2980b9',
    'intermedio': '#b7950b',
    'punta': '#c0392b',
    'success': '#27ae60',
    'carga': '#27ae60',
    'descarga': '#e74c3c',
    'iusa': '#2e86c1',
    'bg_light': '#f4f7f9',
    'bg_row': '#f8fafb',
    'bg_arbitraje': '#eafaf1',
    'border': '#d5dce3',
    'text_muted': '#7f8c8d',
    'text_dark': '#2c3e50',
    'content_width_in': 10.35,
    'chart_height_in': 3.85,
    # Ancho tabla = título sección (Periodo + Base + Intermedio + Punta + Total)
    'table_cols_in': (1.68, 0.86, 0.86, 0.86, 0.98),
    'logo_width_in': 1.3125,
    'logo_max_height_in': 0.725,
    'logo_col_in': 1.44,
    'gap_chart_table_in': 0.28,
}

def _pdf_ancho_tabla_in():
    return sum(_PDF['table_cols_in'])

def _pdf_ancho_tabla():
    from reportlab.lib.units import inch
    return _pdf_ancho_tabla_in() * inch

def _pdf_styles():
    """Estilos tipográficos del reporte PDF (compacto, una página)."""
    from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
    from reportlab.lib import colors
    from reportlab.lib.enums import TA_CENTER, TA_RIGHT, TA_LEFT

    styles = getSampleStyleSheet()
    styles.add(ParagraphStyle(
        name='PdfTitle', parent=styles['Normal'],
        fontSize=14, fontName='Helvetica-Bold',
        textColor=colors.HexColor(_PDF['primary']),
        alignment=TA_RIGHT, spaceAfter=1, leading=16,
    ))
    styles.add(ParagraphStyle(
        name='PdfSubtitle', parent=styles['Normal'],
        fontSize=8, fontName='Helvetica',
        textColor=colors.HexColor(_PDF['text_muted']),
        alignment=TA_RIGHT, spaceAfter=0, leading=10,
    ))
    styles.add(ParagraphStyle(
        name='PdfSection', parent=styles['Normal'],
        fontSize=9, fontName='Helvetica-Bold',
        textColor=colors.HexColor(_PDF['primary']),
        alignment=TA_LEFT, spaceAfter=0, leading=11,
    ))
    styles.add(ParagraphStyle(
        name='PdfSectionSub', parent=styles['Normal'],
        fontSize=6.5, fontName='Helvetica',
        textColor=colors.HexColor(_PDF['text_muted']),
        alignment=TA_LEFT, spaceAfter=0, leading=8,
    ))
    return styles

def _pdf_guardar_logo(logo_path, archivos_temp):
    """Prepara imagen del logo y devuelve flowable ReportLab."""
    from reportlab.platypus import Image
    from reportlab.lib.units import inch
    from PIL import Image as PILImage

    img_logo = PILImage.open(logo_path)
    logo_width = _PDF['logo_width_in'] * inch
    logo_height = logo_width * (img_logo.height / img_logo.width)
    max_h = _PDF['logo_max_height_in'] * inch
    if logo_height > max_h:
        logo_height = max_h
        logo_width = max_h * (img_logo.width / img_logo.height)
    logo_temp = os.path.join(DIRECTORIO_REPORTES_DIARIOS, 'temp_logo.png')
    img_logo.save(logo_temp, 'PNG', quality=95)
    archivos_temp.append(logo_temp)
    return Image(logo_temp, width=logo_width, height=logo_height)

def _pdf_encabezado(story, styles, logo_path, fecha_espanol, archivos_temp):
    """Cabecera con logo, título y franja de color."""
    from reportlab.platypus import Table, TableStyle, Spacer, Paragraph
    from reportlab.lib import colors
    from reportlab.lib.units import inch

    titulo = Paragraph('Reporte Diario BESS', styles['PdfTitle'])
    fecha_p = Paragraph(fecha_espanol, styles['PdfSubtitle'])
    ubicacion = Paragraph('Pastejé, Jocotitlán, Estado de México', styles['PdfSubtitle'])
    cw = _PDF['content_width_in'] * inch

    if logo_path:
        try:
            logo_img = _pdf_guardar_logo(logo_path, archivos_temp)
            info_cell = [[titulo], [fecha_p], [ubicacion]]
            logo_col = _PDF['logo_col_in'] * inch
            info_tbl = Table(info_cell, colWidths=[cw - logo_col])
            info_tbl.setStyle(TableStyle([
                ('ALIGN', (0, 0), (-1, -1), 'RIGHT'),
                ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
                ('TOPPADDING', (0, 0), (-1, -1), 1),
                ('BOTTOMPADDING', (0, 0), (-1, -1), 1),
            ]))
            header = Table([[logo_img, info_tbl]], colWidths=[logo_col, cw - logo_col])
            header.setStyle(TableStyle([
                ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
                ('LEFTPADDING', (0, 0), (-1, -1), 0),
                ('RIGHTPADDING', (0, 0), (-1, -1), 0),
                ('TOPPADDING', (0, 0), (-1, -1), 0),
                ('BOTTOMPADDING', (0, 0), (-1, -1), 0),
            ]))
            story.append(header)
        except Exception as e:
            print(f"Error al cargar logo: {e}")
            story.append(titulo)
            story.append(fecha_p)
            story.append(ubicacion)
    else:
        story.append(titulo)
        story.append(fecha_p)
        story.append(ubicacion)

    linea = Table([['']], colWidths=[cw], rowHeights=[2])
    linea.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, -1), colors.HexColor(_PDF['primary'])),
        ('TOPPADDING', (0, 0), (-1, -1), 0),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 0),
    ]))
    story.append(Spacer(1, 0.04 * inch))
    story.append(linea)
    story.append(Spacer(1, 0.06 * inch))

def _pdf_grafica_perfil(df_dia, prefijo, fecha_dt, archivos_temp):
    """Genera gráfica de perfil de carga con estilo alineado al dashboard."""
    import matplotlib.pyplot as plt
    import matplotlib.dates as mdates
    from reportlab.platypus import Image
    from reportlab.lib.units import inch
    from PIL import Image as PILImage

    horas = df_dia['DATETIME'].values
    iusa_con = df_dia[f'IUSA_CON_BESS_{prefijo}_kW'].values
    bess_rec = df_dia['BESS_REC_kW'].values
    bess_ent = -df_dia['BESS_ENT_kW'].values

    fig, ax = plt.subplots(figsize=(11, 3.62), facecolor='white', dpi=120)
    ax.set_facecolor('white')

    ax.fill_between(horas, 0, iusa_con, alpha=0.12, color=_PDF['iusa'])
    ax.fill_between(horas, 0, bess_rec, alpha=0.15, color=_PDF['carga'])
    ax.fill_between(horas, bess_ent, 0, alpha=0.15, color=_PDF['descarga'])

    ax.plot(horas, iusa_con, color=_PDF['iusa'], linewidth=1.8, label='Demanda con BESS')
    ax.plot(horas, bess_rec, color=_PDF['carga'], linewidth=1.5, label='Carga BESS')
    ax.plot(horas, bess_ent, color=_PDF['descarga'], linewidth=1.5, label='Descarga BESS')

    ax.set_title(
        'Perfil de carga del día',
        fontsize=11, fontweight='bold', color=_PDF['primary'],
        loc='center', pad=26,
    )
    handles, labels = ax.get_legend_handles_labels()
    ax.legend(
        handles, labels,
        loc='lower center', bbox_to_anchor=(0.5, 1.0), ncol=3,
        fontsize=7, frameon=True, facecolor='white',
        edgecolor=_PDF['border'], framealpha=0.95,
        borderpad=0.35, labelspacing=0.35, handlelength=1.4,
    )

    ax.set_xlabel('Hora', fontsize=8, color=_PDF['text_dark'], labelpad=2)
    ax.set_ylabel('Potencia (kW)', fontsize=8, color=_PDF['text_dark'], labelpad=2)
    ax.grid(True, axis='y', alpha=0.35, color=_PDF['border'], linestyle='-', linewidth=0.5)
    ax.grid(True, axis='x', alpha=0.2, color=_PDF['border'], linestyle='-', linewidth=0.4)
    ax.spines['top'].set_visible(False)
    ax.spines['right'].set_visible(False)
    ax.spines['left'].set_color(_PDF['border'])
    ax.spines['bottom'].set_color(_PDF['border'])
    ax.tick_params(colors=_PDF['text_muted'], labelsize=7, pad=1)
    ax.xaxis.set_major_formatter(mdates.DateFormatter('%H:%M'))
    ax.xaxis.set_major_locator(mdates.HourLocator(interval=2))
    plt.setp(ax.xaxis.get_majorticklabels(), rotation=35, ha='right')

    fig.subplots_adjust(top=0.78, bottom=0.16, left=0.07, right=0.98)
    buf = io.BytesIO()
    plt.savefig(buf, format='png', dpi=150, bbox_inches='tight', facecolor='white', edgecolor='none', pad_inches=0.04)
    buf.seek(0)
    plt.close(fig)

    img_path = os.path.join(
        DIRECTORIO_REPORTES_DIARIOS,
        f'temp_perfil_{prefijo}_{fecha_dt.strftime("%Y%m%d")}.png',
    )
    archivos_temp.append(img_path)
    img = PILImage.open(buf)
    img.save(img_path, 'PNG', quality=90, dpi=(150, 150))
    cw = _PDF['content_width_in'] * inch
    ch = _PDF['chart_height_in'] * inch
    return Image(img_path, width=cw, height=ch)

def _pdf_titulo_seccion(story, styles, titulo, subtitulo=''):
    """Título de sección con barra lateral de acento."""
    from reportlab.platypus import Table, TableStyle, Spacer, Paragraph
    from reportlab.lib import colors
    from reportlab.lib.units import inch

    filas = [[Paragraph(titulo, styles['PdfSection'])]]
    if subtitulo:
        filas.append([Paragraph(subtitulo, styles['PdfSectionSub'])])
    tbl = Table(filas, colWidths=[_pdf_ancho_tabla()])
    tbl.setStyle(TableStyle([
        ('LINEBEFORE', (0, 0), (0, -1), 3, colors.HexColor(_PDF['primary'])),
        ('LEFTPADDING', (0, 0), (-1, -1), 8),
        ('TOPPADDING', (0, 0), (-1, -1), 0),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 0),
    ]))
    story.append(tbl)
    story.append(Spacer(1, 0.12 * inch))

def _pdf_tabla_energia(data):
    """Tabla de detalle de energía con columnas por periodo tarifario."""
    from reportlab.platypus import Table, TableStyle
    from reportlab.lib import colors
    from reportlab.lib.units import inch

    n_filas = len(data)
    cols = [w * inch for w in _PDF['table_cols_in']]
    tabla = Table(data, colWidths=cols)
    estilo = TableStyle([
        ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
        ('FONTSIZE', (0, 0), (-1, 0), 9.5),
        ('TEXTCOLOR', (0, 0), (-1, 0), colors.white),
        ('ALIGN', (0, 0), (0, 0), 'LEFT'),
        ('ALIGN', (1, 0), (-1, 0), 'CENTER'),
        ('BACKGROUND', (0, 0), (0, 0), colors.HexColor(_PDF['primary'])),
        ('BACKGROUND', (1, 0), (1, 0), colors.HexColor(_PDF['base'])),
        ('BACKGROUND', (2, 0), (2, 0), colors.HexColor(_PDF['intermedio'])),
        ('BACKGROUND', (3, 0), (3, 0), colors.HexColor(_PDF['punta'])),
        ('BACKGROUND', (4, 0), (4, 0), colors.HexColor(_PDF['text_dark'])),
        ('FONTNAME', (0, 1), (-1, -1), 'Helvetica'),
        ('FONTSIZE', (0, 1), (-1, -1), 8.5),
        ('TEXTCOLOR', (0, 1), (-1, -1), colors.HexColor(_PDF['text_dark'])),
        ('ALIGN', (0, 1), (0, -1), 'LEFT'),
        ('ALIGN', (1, 1), (-1, -1), 'RIGHT'),
        ('FONTNAME', (0, 1), (0, -1), 'Helvetica-Bold'),
        ('FONTNAME', (4, 1), (4, -1), 'Helvetica-Bold'),
        ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
        ('TOPPADDING', (0, 0), (-1, -1), 3),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 3),
        ('LEFTPADDING', (0, 0), (-1, -1), 4),
        ('RIGHTPADDING', (0, 0), (-1, -1), 4),
        ('BOX', (0, 0), (-1, -1), 0.5, colors.HexColor(_PDF['border'])),
        ('LINEBELOW', (0, 0), (-1, 0), 0.8, colors.HexColor(_PDF['primary'])),
        ('INNERGRID', (0, 0), (-1, -1), 0.25, colors.HexColor(_PDF['border'])),
    ])
    # Filas alternadas
    for i in range(1, n_filas):
        if i % 2 == 0:
            estilo.add('BACKGROUND', (0, i), (-1, i), colors.HexColor(_PDF['bg_row']))
    # Fila de arbitraje (última)
    estilo.add('BACKGROUND', (0, n_filas - 1), (-1, n_filas - 1), colors.HexColor(_PDF['bg_arbitraje']))
    estilo.add('FONTNAME', (0, n_filas - 1), (-1, n_filas - 1), 'Helvetica-Bold')
    estilo.add('TEXTCOLOR', (0, n_filas - 1), (0, n_filas - 1), colors.HexColor(_PDF['success']))
    estilo.add('TEXTCOLOR', (4, n_filas - 1), (4, n_filas - 1), colors.HexColor(_PDF['success']))
    tabla.setStyle(estilo)
    return tabla

def _pdf_dibujar_pie(canvas, doc):
    """Pie de página fijo (no ocupa espacio en el flujo del contenido)."""
    from reportlab.lib import colors
    from reportlab.lib.units import inch
    from datetime import datetime as dt_now

    canvas.saveState()
    y_text = doc.bottomMargin - 16
    canvas.setFont('Helvetica', 6)
    canvas.setFillColor(colors.HexColor(_PDF['text_muted']))
    linea1 = 'Carretera Panamericana México–Querétaro S/N km. 100 · Pastejé, Jocotitlán, Estado de México'
    linea2 = f'Sistema BESS · Generado el {dt_now.now().strftime("%d/%m/%Y %H:%M")}'
    cx = doc.pagesize[0] / 2
    canvas.drawCentredString(cx, y_text + 7, linea1)
    canvas.drawCentredString(cx, y_text, linea2)
    canvas.restoreState()

def generar_reporte_pdf(fecha_str, medidor):
    """Genera un reporte PDF para una fecha específica"""
    try:
        from reportlab.lib.pagesizes import letter, landscape
        from reportlab.platypus import SimpleDocTemplate, Spacer
        from reportlab.lib.units import inch

        prefijo = 'ION' if medidor == 'ION' else 'BANCO'

        ruta_combinado = os.path.join(DIRECTORIO_REPORTES, f'COMBINADO_POR_MINUTO_{prefijo}.csv')
        ruta_acumulados = os.path.join(DIRECTORIO_REPORTES, f'ACUMULADOS_{prefijo}.csv')

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

        nombre_archivo = f'Reporte_{medidor}_{fecha_dt.strftime("%Y%m%d")}.pdf'
        ruta_pdf = os.path.join(DIRECTORIO_REPORTES_DIARIOS, nombre_archivo)
        os.makedirs(DIRECTORIO_REPORTES_DIARIOS, exist_ok=True)

        doc = SimpleDocTemplate(
            ruta_pdf, pagesize=landscape(letter),
            rightMargin=18, leftMargin=18,
            topMargin=14, bottomMargin=32,
        )

        styles = _pdf_styles()
        archivos_temp = []
        story = []

        logo_path = buscar_logo()
        fecha_espanol = formatear_fecha_espanol(fecha_dt)
        _pdf_encabezado(story, styles, logo_path, fecha_espanol, archivos_temp)

        story.append(_pdf_grafica_perfil(df_dia, prefijo, fecha_dt, archivos_temp))
        story.append(Spacer(1, _PDF['gap_chart_table_in'] * inch))

        _pdf_titulo_seccion(
            story, styles,
            'Detalle de Energía',
            f'Acumulado mensual al {fecha_str} · Arbitraje del día {fecha_str}',
        )

        tarifas = cargar_tarifas()

        if os.path.exists(ruta_acumulados):
            df_acum = pd.read_csv(ruta_acumulados)
            fila_acum = df_acum[df_acum['FECHA'] == fecha_str]
        else:
            fila_acum = None

        data = [['Periodo', 'Base', 'Intermedio', 'Punta', 'Total']]

        if fila_acum is not None and len(fila_acum) > 0:
            fila = fila_acum.iloc[0]
            consumo_base = _a_num(fila.get('BASE_REC_ACUM', 0))
            consumo_intermedio = _a_num(fila.get('INTERMEDIO_REC_ACUM', 0))
            consumo_punta = _a_num(fila.get('PUNTA_REC_ACUM', 0))
            demanda_base = redondear_arriba_kw(fila.get('BASE_DEM_CON_BESS_MAX', 0))
            demanda_intermedio = redondear_arriba_kw(fila.get('INTERMEDIO_DEM_CON_BESS_MAX', 0))
            demanda_punta = redondear_arriba_kw(fila.get('PUNTA_DEM_CON_BESS_MAX', 0))
        else:
            consumo_base = consumo_intermedio = consumo_punta = 0
            demanda_base = demanda_intermedio = demanda_punta = 0

        bess_dia = obtener_bess_energia_dia(fecha_str)
        c_b, c_i, c_p, c_t = _celdas_kwh_tabla(consumo_base, consumo_intermedio, consumo_punta)
        g_b, g_i, g_p, g_t = _celdas_kwh_tabla(
            bess_dia['carga_base'], bess_dia['carga_intermedio'], bess_dia['carga_punta']
        )
        d_b, d_i, d_p, d_t = _celdas_kwh_tabla(
            bess_dia['descarga_base'], bess_dia['descarga_intermedio'], bess_dia['descarga_punta']
        )

        data.append(['Consumo Mensual (kWh)', c_b, c_i, c_p, c_t])
        data.append(['Demanda Rolada (kW)', f'{demanda_base:,}', f'{demanda_intermedio:,}', f'{demanda_punta:,}', f'{demanda_punta:,}'])
        data.append(['Carga del día BESS (kWh)', g_b, g_i, g_p, g_t])
        data.append(['Descarga del día BESS (kWh)', d_b, d_i, d_p, d_t])

        arb = calcular_arbitraje_dia(fecha_str, prefijo, tarifas=tarifas)
        data.append([
            'Arbitraje del día (MXN)',
            f'${arb["base"]:,.2f}', f'${arb["intermedio"]:,.2f}',
            f'${arb["punta"]:,.2f}', f'${arb["total"]:,.2f}',
        ])

        story.append(_pdf_tabla_energia(data))

        doc.build(story, onFirstPage=_pdf_dibujar_pie, onLaterPages=_pdf_dibujar_pie)

        for archivo in archivos_temp:
            if os.path.exists(archivo):
                try:
                    os.remove(archivo)
                except Exception:
                    pass

        return True, ruta_pdf

    except Exception as e:
        return False, str(e)
    

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
    
    print("\n" + "=" * 60)
    print("RESUMEN DEL PROCESO")
    print("=" * 60)
    print("\nGRUPO 1: BESS vs ION - " + ("✅ Éxito" if resultado_ion else "❌ Falló"))
    print("GRUPO 2: BESS vs BANCO1 - " + ("✅ Éxito" if resultado_banco else "❌ Falló"))
    print("\n" + "=" * 60)
    print("=== FIN DEL PROCESO ===")
    
    return resultado_ion and resultado_banco, msg_ion, msg_banco