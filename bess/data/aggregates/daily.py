"""Agregados diarios con demandas."""

from __future__ import annotations

import os

import pandas as pd

from bess.config.paths import DIRECTORIO_REPORTES
from bess.cfe.periods import obtener_periodo_por_fecha_hora
from bess.core.kvarh import (
    columnas_kvarh as _columnas_kvarh,
    kvarh_total as _kvarh_total,
    normalizar_columnas_kvarh as _normalizar_columnas_kvarh,
)
from bess.core.console import log

print = log

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
