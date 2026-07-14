"""Combinado por minuto de medidores."""

from __future__ import annotations

import os

from datetime import datetime

import pandas as pd

from bess.config.subestaciones import medidor_consumo_por_prefijo
from bess.cfe.periods import periodo_por_fecha_hora
from bess.config.esquema_tarifa import esquema_tarifa_prefijo, normalizar_esquema_tarifa
from bess.core.consumo import kwh_neto_consumo, usa_consumo_neto
from bess.core.dates import agregar_fecha_operativa
from bess.core.demand import demanda_rodante_15min_por_mes
from bess.core.kvarh import columnas_kvarh as _columnas_kvarh
from bess.data.ingest.readers import leer_sin_agrupar

from bess.core.console import log
print = log


def generar_combinado_por_minuto(ruta_bess, ruta_medidor, prefijo, esquema_tarifa_id=None):
    """Genera COMBINADO_POR_MINUTO.csv con resolución de 5 minutos"""
    print("\n" + "=" * 60)
    print(f"GENERANDO COMBINADO_POR_MINUTO_{prefijo}.csv")
    print("=" * 60)

    df_bess = leer_sin_agrupar(ruta_bess)
    df_medidor = leer_sin_agrupar(ruta_medidor, prefijo_consumo=prefijo)

    col_rec = f"KWH_REC_{prefijo}"
    col_ent = f"KWH_ENT_{prefijo}"
    if "KWH_REC" not in df_medidor.columns and col_rec in df_medidor.columns:
        df_medidor = df_medidor.copy()
        df_medidor["KWH_REC"] = df_medidor[col_rec]
    if "KWH_ENT" not in df_medidor.columns and col_ent in df_medidor.columns:
        df_medidor = df_medidor.copy()
        df_medidor["KWH_ENT"] = df_medidor[col_ent]

    if usa_consumo_neto(prefijo):
        print(f"  {prefijo}: energía y demanda con KWH_NETO (max(0, REC-ENT))")

    print(f"  BESS: {len(df_bess)} registros")
    print(f"  {prefijo}: {len(df_medidor)} registros")

    cols_ion = ["FECHA_HORA", "KWH_REC", "KWH_ENT"]
    if usa_consumo_neto(prefijo) and "KWH_NETO" in df_medidor.columns:
        cols_ion.append("KWH_NETO")
    for col in _columnas_kvarh(df_medidor):
        if col not in cols_ion:
            cols_ion.append(col)
    df_ion = df_medidor[cols_ion].rename(
        columns={
            "KWH_REC": f"KWH_REC_{prefijo}",
            "KWH_ENT": f"KWH_ENT_{prefijo}",
        }
    )

    df_combinado = pd.merge(
        df_bess[["FECHA_HORA", "KWH_REC", "KWH_ENT"]].rename(
            columns={"KWH_REC": "KWH_REC_BESS", "KWH_ENT": "KWH_ENT_BESS"}
        ),
        df_ion,
        on="FECHA_HORA",
        how="inner",
    )

    print(f"  Registros combinados: {len(df_combinado)}")

    esquema = normalizar_esquema_tarifa(esquema_tarifa_id or esquema_tarifa_prefijo(prefijo))

    horas = []
    for _, row in df_combinado.iterrows():
        dt = datetime.strptime(row["FECHA_HORA"], "%d/%m/%Y %H:%M")
        hora = dt.hour
        if hora == 0:
            hora = 24
        horas.append(hora)
    df_combinado["HORA"] = horas

    periodos = []
    for _, row in df_combinado.iterrows():
        periodo = periodo_por_fecha_hora(row["FECHA_HORA"], esquema)
        periodos.append(periodo)
    df_combinado["PERIODO"] = periodos

    df_combinado["BESS_REC_kW"] = df_combinado["KWH_REC_BESS"] * 12
    df_combinado["BESS_ENT_kW"] = df_combinado["KWH_ENT_BESS"] * 12

    if usa_consumo_neto(prefijo) and "KWH_NETO" not in df_combinado.columns:
        col_rec = f"KWH_REC_{prefijo}"
        col_ent = f"KWH_ENT_{prefijo}"
        if col_rec in df_combinado.columns and col_ent in df_combinado.columns:
            df_combinado["KWH_NETO"] = (
                pd.to_numeric(df_combinado[col_rec], errors="coerce").fillna(0)
                - pd.to_numeric(df_combinado[col_ent], errors="coerce").fillna(0)
            ).clip(lower=0)

    col_con = f"IUSA_CON_BESS_{prefijo}_kW"
    col_sin = f"IUSA_SIN_BESS_{prefijo}_kW"
    kwh_ion = kwh_neto_consumo(df_combinado, prefijo)
    df_combinado[col_con] = kwh_ion * 12
    df_combinado[col_sin] = (
        kwh_ion
        - pd.to_numeric(df_combinado["KWH_REC_BESS"], errors="coerce").fillna(0)
        + pd.to_numeric(df_combinado["KWH_ENT_BESS"], errors="coerce").fillna(0)
    ) * 12

    df_combinado["BESS_NETO_kWh"] = (
        df_combinado["KWH_REC_BESS"] - df_combinado["KWH_ENT_BESS"]
    )
    df_combinado[f"{prefijo}_NETO_kWh"] = kwh_neto_consumo(df_combinado, prefijo)
    df_combinado[f"Mejora_BESS_{prefijo}_kWh"] = (
        df_combinado[f"{prefijo}_NETO_kWh"] - df_combinado["BESS_NETO_kWh"]
    )
    df_combinado[f"Mejora_BESS_{prefijo}_kW"] = (
        df_combinado[f"Mejora_BESS_{prefijo}_kWh"] * 12
    )

    print("\n--- Calculando demanda rodante (rolling 15 min, reinicio mensual) ---")
    df_combinado = agregar_fecha_operativa(df_combinado, col_fecha_hora="FECHA_HORA")
    mes_operativo = pd.to_datetime(df_combinado["FECHA"], format="%d/%m/%Y").dt.to_period("M")
    for col in (col_con, col_sin):
        col_demanda = f"{col}_DEM_15min"
        df_combinado[col_demanda] = demanda_rodante_15min_por_mes(
            df_combinado[col], mes_operativo
        )

    columnas_export = [
        "FECHA",
        "FECHA_HORA",
        "PERIODO",
        "KWH_REC_BESS",
        "KWH_ENT_BESS",
        "BESS_REC_kW",
        "BESS_ENT_kW",
        f"KWH_REC_{prefijo}",
        f"KWH_ENT_{prefijo}",
    ]
    if usa_consumo_neto(prefijo) and "KWH_NETO" in df_combinado.columns:
        columnas_export.append("KWH_NETO")
    for col in _columnas_kvarh(df_combinado):
        if col not in columnas_export:
            columnas_export.append(col)
    columnas_export.extend([
        col_con,
        f"{col_con}_DEM_15min",
        f"{col_sin}_DEM_15min",
    ])

    med = medidor_consumo_por_prefijo(prefijo)
    if not med:
        print(f"ERROR: medidor de consumo desconocido: {prefijo}")
        return None
    ruta_salida = str(med.ruta_combinado())
    nombre_archivo = med.ruta_combinado().name
    os.makedirs(os.path.dirname(ruta_salida), exist_ok=True)
    df_combinado[columnas_export].to_csv(ruta_salida, index=False)

    print(f"OK {nombre_archivo} - {len(df_combinado)} registros")
    return df_combinado
