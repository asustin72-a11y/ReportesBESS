"""Reporte diario BESS por subestación."""

from __future__ import annotations

import os

import pandas as pd

from bess.config.subestaciones import Subestacion, medidor_consumo_por_prefijo, ruta_combinado_por_prefijo
from bess.cfe.periods import periodo_por_fecha_hora
from bess.config.esquema_tarifa import normalizar_esquema_tarifa
from bess.core.atomic_io import ruta_temporal_atomica
from bess.core.dates import agregar_fecha_operativa
from bess.data.aggregates._incremental_dia import (
    columnas_dia,
    combinar_cola_diaria,
    cursor_dia,
)
from bess.core.console import log

print = log

# Fijo: permite comparar contra el encabezado de un ENERGIA_BESS_*.csv
# existente para decidir si el recálculo incremental aplica (ver
# _incremental_dia.py).
COLUMNAS_BESS_DIARIO = [
    "FECHA",
    "BASE_REC",
    "INTERMEDIO_REC",
    "PUNTA_REC",
    "BASE_ENT",
    "INTERMEDIO_ENT",
    "PUNTA_ENT",
]


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


def _bess_diario_desde_combinado_minuto(
    prefijo: str, esquema_tarifa_id: str, *, cursor: "pd.Timestamp | None" = None
) -> pd.DataFrame | None:
    """Carga/descarga BESS por periodo desde COMBINADO_POR_MINUTO (5 min).

    Si `cursor` no es None, solo se agregan las filas con FECHA >= cursor
    (recálculo incremental: el último día ya escrito, por si seguía
    abierto, más los días nuevos). Devuelve un DataFrame vacío (con las
    columnas esperadas) si no hay filas en ese rango -- "sin días nuevos",
    no un error.
    """
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
        df["PERIODO"] = df["FECHA_HORA"].apply(
            lambda fh: periodo_por_fecha_hora(fh, esquema_tarifa_id)
        )

    if cursor is not None:
        fecha_dt = pd.to_datetime(df["FECHA"], format="%d/%m/%Y")
        df = df[fecha_dt >= cursor]
        if df.empty:
            return pd.DataFrame(columns=COLUMNAS_BESS_DIARIO)

    df_bess_dia = df.groupby(["FECHA", "PERIODO"], as_index=False).agg(
        KWH_REC=("KWH_REC_BESS", "sum"),
        KWH_ENT=("KWH_ENT_BESS", "sum"),
    )
    return _pivot_bess_periodos(df_bess_dia)


def _guardar_bess_diario(df: pd.DataFrame, ruta_salida: str, etiqueta: str) -> pd.DataFrame:
    os.makedirs(os.path.dirname(ruta_salida), exist_ok=True)
    # Escritura atómica (bess.core.atomic_io): si algo interrumpe esta
    # escritura a medio camino, ruta_salida conserva su contenido anterior
    # en vez de quedar truncado.
    with ruta_temporal_atomica(ruta_salida) as ruta_temp:
        df.to_csv(ruta_temp, index=False)
    print(f"OK {etiqueta} - {len(df)} dias (desde COMBINADO_POR_MINUTO)")
    return df


def generar_bess_diario_subestacion(sub: Subestacion):
    """Genera ENERGIA_BESS_{sub}.csv desde el combinado del medidor de
    facturación.

    Incremental: igual que daily.py, cada día es independiente (sin
    ventana ni acumulado entre días), así que si el reporte ya existe con
    cursor legible y columnas compatibles, solo se recalcula el último
    día ya escrito (por si seguía abierto) en adelante.
    """
    if not sub.medidores_consumo:
        return None
    med_fact = sub.medidor_facturacion
    if not med_fact:
        return None
    nombre = sub.ruta_energia_bess_dia().name
    ruta_salida = str(sub.ruta_energia_bess_dia())
    print(f"\n--- GENERANDO {nombre} ({sub.id}) ---")

    esquema = normalizar_esquema_tarifa(sub.esquema_tarifa_id)

    cursor = cursor_dia(ruta_salida)
    incremental = cursor is not None and columnas_dia(ruta_salida) == COLUMNAS_BESS_DIARIO

    df_bess_diario = _bess_diario_desde_combinado_minuto(
        med_fact.prefijo, esquema, cursor=cursor if incremental else None
    )
    if df_bess_diario is None:
        print(f"ERROR: No se pudo generar desde combinado de {med_fact.nombre}")
        return None

    if incremental:
        if df_bess_diario.empty:
            print(f"  Sin días nuevos para {nombre} (cursor {cursor.date()})")
            return pd.read_csv(ruta_salida)
        df_bess_diario = combinar_cola_diaria(df_bess_diario, ruta_salida, COLUMNAS_BESS_DIARIO)

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
