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
