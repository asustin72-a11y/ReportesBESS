"""Lectura de perfiles CSV (sin agrupar / por hora)."""

from __future__ import annotations

import os

import numpy as np
import pandas as pd

from bess.core.dates import validar_y_convertir_fecha
from bess.core.kvarh import (
    columnas_kvarh as _columnas_kvarh,
    normalizar_columnas_kvarh as _normalizar_columnas_kvarh,
)

from bess.core.console import log
print = log

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
