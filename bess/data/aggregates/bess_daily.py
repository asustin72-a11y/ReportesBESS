"""Reporte diario BESS por subestación."""

from __future__ import annotations

import os

import pandas as pd

from bess.config.subestaciones import Subestacion, medidor_consumo_por_prefijo, ruta_combinado_por_prefijo
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
    med = medidor_consumo_por_prefijo(prefijo)
    if not med:
        return None
    ruta_p = ruta_combinado_por_prefijo(prefijo)
    if not ruta_p or not ruta_p.exists():
        return None
    ruta = str(ruta_p)

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
    os.makedirs(os.path.dirname(ruta_salida), exist_ok=True)
    df.to_csv(ruta_salida, index=False)
    print(f"OK {etiqueta} - {len(df)} dias (desde COMBINADO_POR_MINUTO)")
    return df


def generar_bess_diario_subestacion(sub: Subestacion):
    """Genera ENERGIA_BESS_{sub}.csv desde el combinado del medidor de facturación."""
    if not sub.medidores_consumo:
        return None
    med_fact = sub.medidores_consumo[0]
    nombre = sub.ruta_energia_bess_dia().name
    ruta_salida = str(sub.ruta_energia_bess_dia())
    print(f"\n--- GENERANDO {nombre} ({sub.id}) ---")

    df_bess_diario = _bess_diario_desde_combinado_minuto(med_fact.prefijo)
    if df_bess_diario is None:
        print(f"ERROR: No se pudo generar desde combinado de {med_fact.nombre}")
        return None
    return _guardar_bess_diario(df_bess_diario, ruta_salida, nombre)


def generar_bess_diario():
    """Compatibilidad: primera subestación con medidor ION."""
    from bess.config.subestaciones import SUBESTACIONES

    for sub in SUBESTACIONES:
        return generar_bess_diario_subestacion(sub)
    return None


def generar_bess_diario_prefijo(prefijo: str):
    """Compatibilidad: BESS diario de la subestación del prefijo."""
    from bess.config.subestaciones import subestacion_por_prefijo

    sub = subestacion_por_prefijo(prefijo)
    if sub:
        return generar_bess_diario_subestacion(sub)
    return None
