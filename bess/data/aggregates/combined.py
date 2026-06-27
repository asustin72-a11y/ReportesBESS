"""Combinado por minuto de medidores."""

from __future__ import annotations

import os

from datetime import datetime

import pandas as pd

from bess.config.paths import DIRECTORIO_REPORTES
from bess.cfe.periods import obtener_periodo_por_fecha_hora
from bess.data.ingest.readers import leer_sin_agrupar

from bess.core.console import log
print = log

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
