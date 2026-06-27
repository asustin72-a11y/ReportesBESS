"""Reporte diario BESS."""

from __future__ import annotations

import os

import pandas as pd

from bess.config.paths import DIRECTORIO_REPORTES
from bess.core.console import log

print = log

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
