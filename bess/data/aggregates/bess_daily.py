"""Reporte diario BESS."""

from __future__ import annotations

import os

import pandas as pd

from bess.config.paths import DIRECTORIO_REPORTES, nombre_energia_bess_por_dia
from bess.cfe.periods import obtener_periodo_por_fecha_hora
from bess.core.dates import agregar_fecha_operativa
from bess.core.console import log

print = log


def _pivot_bess_periodos(df_bess_dia: pd.DataFrame) -> pd.DataFrame:
    """Pivotea FECHA × PERIODO → columnas BASE_/INTERMEDIO_/PUNTA_ REC y ENT."""
    df_bess_rec_pivot = df_bess_dia.pivot_table(
        index="FECHA", columns="PERIODO", values="KWH_REC", aggfunc="sum", fill_value=0,
    ).reset_index()
    df_bess_rec_pivot = df_bess_rec_pivot.rename(columns={
        "Base": "BASE_REC", "Intermedio": "INTERMEDIO_REC", "Punta": "PUNTA_REC",
    })

    df_bess_ent_pivot = df_bess_dia.pivot_table(
        index="FECHA", columns="PERIODO", values="KWH_ENT", aggfunc="sum", fill_value=0,
    ).reset_index()
    df_bess_ent_pivot = df_bess_ent_pivot.rename(columns={
        "Base": "BASE_ENT", "Intermedio": "INTERMEDIO_ENT", "Punta": "PUNTA_ENT",
    })

    for col in ("BASE_REC", "INTERMEDIO_REC", "PUNTA_REC"):
        if col not in df_bess_rec_pivot.columns:
            df_bess_rec_pivot[col] = 0.0
    for col in ("BASE_ENT", "INTERMEDIO_ENT", "PUNTA_ENT"):
        if col not in df_bess_ent_pivot.columns:
            df_bess_ent_pivot[col] = 0.0

    df_bess_diario = df_bess_rec_pivot.merge(df_bess_ent_pivot, on="FECHA", how="outer").fillna(0)
    df_bess_diario["FECHA_DT"] = pd.to_datetime(df_bess_diario["FECHA"], format="%d/%m/%Y")
    return df_bess_diario.sort_values("FECHA_DT").drop("FECHA_DT", axis=1)


def _bess_diario_desde_combinado_minuto(prefijo: str) -> pd.DataFrame | None:
    """Carga/descarga BESS por periodo desde COMBINADO_POR_MINUTO (5 min)."""
    ruta = os.path.join(DIRECTORIO_REPORTES, f"COMBINADO_POR_MINUTO_{prefijo}.csv")
    if not os.path.exists(ruta):
        return None

    df = pd.read_csv(ruta)
    if "KWH_REC_BESS" not in df.columns or "KWH_ENT_BESS" not in df.columns:
        return None

    if "FECHA" not in df.columns:
        df = agregar_fecha_operativa(df, col_fecha_hora="FECHA_HORA")
    if "PERIODO" not in df.columns:
        df["PERIODO"] = df["FECHA_HORA"].apply(obtener_periodo_por_fecha_hora)

    df_bess_dia = df.groupby(["FECHA", "PERIODO"], as_index=False).agg(
        KWH_REC=("KWH_REC_BESS", "sum"),
        KWH_ENT=("KWH_ENT_BESS", "sum"),
    )
    return _pivot_bess_periodos(df_bess_dia)


def _guardar_bess_diario(df: pd.DataFrame, ruta_salida: str, etiqueta: str) -> pd.DataFrame:
    df.to_csv(ruta_salida, index=False)
    print(f"OK {etiqueta} - {len(df)} dias (desde COMBINADO_POR_MINUTO)")
    return df


def generar_bess_diario():
    """Genera ENERGIA_BESS_POR_DIA.csv (IUSA 1 · archivo general, medidor ION)."""
    print("\n" + "=" * 60)
    print("GENERANDO ENERGIA_BESS_POR_DIA.csv")
    print("=" * 60)

    ruta_salida = os.path.join(DIRECTORIO_REPORTES, "ENERGIA_BESS_POR_DIA.csv")
    df_bess_diario = _bess_diario_desde_combinado_minuto("ION")
    if df_bess_diario is None:
        print("ERROR: No se pudo generar desde COMBINADO_POR_MINUTO_ION.csv")
        return None
    return _guardar_bess_diario(df_bess_diario, ruta_salida, "ENERGIA_BESS_POR_DIA.csv")


def generar_bess_diario_prefijo(prefijo: str):
    """Genera ENERGIA_BESS_POR_DIA*.csv desde COMBINADO_POR_MINUTO (5 min)."""
    nombre = nombre_energia_bess_por_dia(prefijo)
    ruta_salida = os.path.join(DIRECTORIO_REPORTES, nombre)
    print(f"\n--- GENERANDO {nombre} ({prefijo}) ---")

    df_bess_diario = _bess_diario_desde_combinado_minuto(prefijo)
    if df_bess_diario is None:
        print(f"ERROR: No se pudo generar desde COMBINADO_POR_MINUTO_{prefijo}.csv")
        return None
    return _guardar_bess_diario(df_bess_diario, ruta_salida, nombre)
