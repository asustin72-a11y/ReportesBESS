"""Acumulados por medidor."""

from __future__ import annotations

import os

import pandas as pd

from bess.config.subestaciones import (
    medidor_consumo_por_prefijo,
    ruta_energia_dia_por_prefijo,
)

from bess.core.console import log
print = log

def generar_acumulados(prefijo):
    """Genera archivos acumulados por mes"""
    print("\n" + "=" * 60)
    print(f"GENERANDO ARCHIVOS ACUMULADOS ({prefijo})")
    print("=" * 60)
    
    med = medidor_consumo_por_prefijo(prefijo)
    ruta_med_dia_p = ruta_energia_dia_por_prefijo(prefijo)
    if not ruta_med_dia_p or not ruta_med_dia_p.exists():
        print(f"ERROR: No se encuentra energía diaria para {prefijo}")
        return None
    ruta_med_dia = str(ruta_med_dia_p)
    if med:
        ruta_salida = str(med.ruta_acumulados())
        nombre_med_acum = med.ruta_acumulados().name
    else:
        nombre_med_acum = f"ACUMULADOS_{prefijo}.csv"
        ruta_salida = nombre_med_acum
    
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

    os.makedirs(os.path.dirname(ruta_salida) or ".", exist_ok=True)
    df_acum_med.to_csv(ruta_salida, index=False)
    print(f"OK {nombre_med_acum} - {len(df_acum_med)} dias (acumulado por mes)")
    
    return df_acum_med
