"""Lectura de perfiles CSV (sin agrupar / por hora)."""

from __future__ import annotations

import os

import numpy as np
import pandas as pd

from bess.core.dates import validar_y_convertir_fecha
from bess.core.consumo import enriquecer_consumo_neto, usa_consumo_neto
from bess.core.kvarh import (
    columnas_kvarh as _columnas_kvarh,
    normalizar_columnas_kvarh as _normalizar_columnas_kvarh,
)

from bess.core.console import log
print = log


def _parsear_columna_fecha(serie: pd.Series) -> pd.Series:
    """Unifica fechas ISO y dd/mm/yyyy (con o sin segundos) desde CSV de perfiles."""
    normalizada = serie.map(validar_y_convertir_fecha)
    return pd.to_datetime(normalizada, errors="coerce")


def _asegurar_columnas_kwh(df: pd.DataFrame) -> pd.DataFrame:
    """Garantiza columnas KWH_REC y KWH_ENT numéricas (nombres alternativos o posición)."""
    out = df.copy()
    if "KWH_REC" in out.columns and "KWH_ENT" in out.columns:
        out["KWH_REC"] = pd.to_numeric(out["KWH_REC"], errors="coerce").fillna(0)
        out["KWH_ENT"] = pd.to_numeric(out["KWH_ENT"], errors="coerce").fillna(0)
        return out

    rec_col = ent_col = None
    for col in out.columns:
        nombre = str(col).lower().replace(" ", "")
        if rec_col is None and nombre in ("kwh_rec", "kwhr", "kw_rec"):
            rec_col = col
        if ent_col is None and nombre in ("kwh_ent", "kwhe", "kw_ent"):
            ent_col = col
    if rec_col is None and len(out.columns) > 1:
        rec_col = out.columns[1]
    if ent_col is None and len(out.columns) > 2:
        ent_col = out.columns[2]

    out["KWH_REC"] = (
        pd.to_numeric(out[rec_col], errors="coerce").fillna(0)
        if rec_col is not None
        else 0.0
    )
    out["KWH_ENT"] = (
        pd.to_numeric(out[ent_col], errors="coerce").fillna(0)
        if ent_col is not None
        else 0.0
    )
    return out


def leer_archivo_perfil(ruta, nombre_archivo):
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
    df["Fecha"] = _parsear_columna_fecha(df["Fecha"])
    
    registros_invalidos = df['Fecha'].isna().sum()
    if registros_invalidos > 0:
        print(f"⚠️ {nombre_archivo}: Se eliminaron {registros_invalidos} registros con fecha inválida")
        df = df.dropna(subset=['Fecha'])
    
    df = _asegurar_columnas_kwh(df)
    df = _normalizar_columnas_kvarh(df)

    print(f"✅ {nombre_archivo}: {len(df)} registros válidos")
    return df


def leer_sin_agrupar(ruta_archivo, prefijo_consumo: str | None = None):
    """Lee el archivo original SIN agrupar (incluye kVArh si existen)."""
    df = pd.read_csv(ruta_archivo, encoding='utf-8-sig')
    columna_fecha = df.columns[0]
    df['DATETIME'] = _parsear_columna_fecha(df[columna_fecha])
    df = df.dropna(subset=['DATETIME']).reset_index(drop=True)

    df = _asegurar_columnas_kwh(df)

    df = _normalizar_columnas_kvarh(df)
    df['FECHA_HORA'] = df['DATETIME'].dt.strftime('%d/%m/%Y %H:%M')

    columnas = ['FECHA_HORA', 'KWH_REC', 'KWH_ENT'] + _columnas_kvarh(df)
    df = df[columnas]
    if prefijo_consumo:
        df = enriquecer_consumo_neto(df, prefijo_consumo)
    return df


def leer_y_agrupar_por_hora(ruta_archivo, nombre_archivo, prefijo_consumo: str | None = None):
    """Lee y agrupa datos por hora (incluye kVArh si existen)."""
    df = pd.read_csv(ruta_archivo, encoding='utf-8-sig')
    columna_fecha = df.columns[0]
    df['DATETIME'] = _parsear_columna_fecha(df[columna_fecha])
    df = df.dropna(subset=['DATETIME']).reset_index(drop=True)

    df = _asegurar_columnas_kwh(df)

    df = _normalizar_columnas_kvarh(df)
    df = df.sort_values('DATETIME').reset_index(drop=True)
    num_registros = len(df)
    num_horas = num_registros // 12

    if num_registros % 12 != 0:
        print(f"  - ADVERTENCIA: {num_registros % 12} registros sobrantes en {nombre_archivo}")
        df = df.iloc[:num_horas * 12].reset_index(drop=True)

    df['GRUPO'] = np.arange(len(df)) // 12

    sumar_neto_por_intervalo = (
        prefijo_consumo is not None and usa_consumo_neto(prefijo_consumo)
    )
    if sumar_neto_por_intervalo:
        df = enriquecer_consumo_neto(df, prefijo_consumo)

    agg = {'DATETIME': 'first', 'KWH_REC': 'sum', 'KWH_ENT': 'sum'}
    if sumar_neto_por_intervalo:
        agg['KWH_NETO'] = 'sum'
    for col in _columnas_kvarh(df):
        agg[col] = 'sum'

    df_agrupado = df.groupby('GRUPO').agg(agg).reset_index(drop=True)

    df_agrupado['HORA'] = df_agrupado['DATETIME'].dt.hour + 1
    df_agrupado['HORA'] = df_agrupado['HORA'].replace(25, 1)
    df_agrupado['FECHA'] = df_agrupado['DATETIME'].dt.strftime('%d/%m/%Y')
    df_agrupado['FECHA_HORA'] = df_agrupado['DATETIME'].dt.strftime('%d/%m/%Y %H:%M')

    columnas = ['FECHA', 'HORA', 'FECHA_HORA', 'KWH_REC', 'KWH_ENT']
    if 'KWH_NETO' in df_agrupado.columns:
        columnas.append('KWH_NETO')
    columnas.extend(_columnas_kvarh(df_agrupado))
    df_agrupado = df_agrupado[columnas]
    if prefijo_consumo and not sumar_neto_por_intervalo:
        df_agrupado = enriquecer_consumo_neto(df_agrupado, prefijo_consumo)
    return df_agrupado

# ========== FUNCIONES DE PROCESAMIENTO ==========
