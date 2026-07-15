"""Generación de archivos limpios desde perfiles."""

from __future__ import annotations

import os

import pandas as pd

from bess.config.paths import DIRECTORIO_PROCESADOS
from bess.core.dates import normalizar_fecha
from bess.core.kvarh import columnas_kvarh as _columnas_kvarh

from bess.core.console import log
print = log

def generar_archivo_limpio(df, ruta_salida):
    """Genera un archivo CSV limpio (conserva kVArh por cuadrante si existen)."""
    columnas = ['Fecha', 'KWH_REC', 'KWH_ENT'] + _columnas_kvarh(df)
    df_limpio = df[columnas].copy()
    df_limpio['Fecha'] = df_limpio['Fecha'].apply(normalizar_fecha)
    df_limpio.to_csv(ruta_salida, index=False, encoding='utf-8-sig')
    print(f"✅ Archivo generado: {ruta_salida} ({len(df_limpio)} registros)")
    return df_limpio


def anexar_archivo_limpio(df, ruta_salida):
    """Agrega filas nuevas al final de un CSV ya escrito por generar_archivo_limpio,
    sin reescribir lo que ya había (mismas columnas del archivo existente).

    Pensado para pasos incrementales (cursor sobre la última Fecha ya
    escrita): quien llama ya filtró `df` a solo las filas nuevas.
    """
    columnas = ['Fecha', 'KWH_REC', 'KWH_ENT'] + _columnas_kvarh(df)
    df_limpio = df[columnas].copy()
    df_limpio['Fecha'] = df_limpio['Fecha'].apply(normalizar_fecha)
    df_limpio.to_csv(ruta_salida, index=False, header=False, mode='a', encoding='utf-8-sig')
    print(f"✅ {len(df_limpio)} registro(s) nuevo(s) anexado(s) a: {ruta_salida}")
    return df_limpio


def columnas_archivo_limpio(ruta_salida) -> list[str] | None:
    """Encabezado de un CSV ya generado, o None si no existe o no se puede leer."""
    if not os.path.exists(ruta_salida):
        return None
    try:
        return list(pd.read_csv(ruta_salida, nrows=0, encoding='utf-8-sig').columns)
    except (ValueError, OSError):
        return None


def cursor_archivo_limpio(ruta_salida) -> "pd.Timestamp | None":
    """Última Fecha ya escrita en un CSV generado por generar_archivo_limpio,
    o None si no existe/está vacío/no tiene una columna Fecha legible."""
    if not os.path.exists(ruta_salida):
        return None
    try:
        fechas = pd.read_csv(
            ruta_salida, usecols=['Fecha'], encoding='utf-8-sig'
        )['Fecha']
    except (ValueError, KeyError, OSError):
        return None
    # dayfirst=True: normalizar_fecha() escribe DD/MM/YYYY, ambiguo para
    # pandas sin esta bandera cuando el dia es <= 12 (p.ej. 01/02/2026).
    fechas = pd.to_datetime(fechas, errors='coerce', dayfirst=True).dropna()
    if fechas.empty:
        return None
    return fechas.max()
