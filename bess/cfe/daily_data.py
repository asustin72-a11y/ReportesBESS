"""Lectura de agregados diarios desde CSV de reportes."""

from __future__ import annotations

import os

import pandas as pd

from bess.config.paths import ruta_energia_bess_por_dia
from bess.config.subestaciones import ruta_energia_dia_por_prefijo
from bess.core.numbers import a_num


def fila_por_fecha_csv(ruta: str, fecha_str: str):
    if not os.path.exists(ruta):
        return None
    df = pd.read_csv(ruta)
    fila = df[df["FECHA"] == fecha_str]
    return fila.iloc[0] if len(fila) > 0 else None


def energia_diaria_tiene_sin_bess(prefijo: str) -> bool:
    ruta_p = ruta_energia_dia_por_prefijo(prefijo)
    if not ruta_p or not ruta_p.exists():
        return False
    return "BASE_REC_SIN_BESS" in pd.read_csv(ruta_p, nrows=0).columns


from bess.data.ingest.medidor_ids import MEDIDOR_ION


def obtener_bess_energia_dia(fecha_str: str, prefijo: str = MEDIDOR_ION) -> dict[str, float]:
    """Carga y descarga BESS del día según subestación (prefijo de facturación)."""
    fila = fila_por_fecha_csv(str(ruta_energia_bess_por_dia(prefijo)), fecha_str)
    if fila is None:
        return {
            "carga_base": 0.0,
            "carga_intermedio": 0.0,
            "carga_punta": 0.0,
            "descarga_base": 0.0,
            "descarga_intermedio": 0.0,
            "descarga_punta": 0.0,
        }
    return {
        "carga_base": a_num(fila.get("BASE_REC", 0)),
        "carga_intermedio": a_num(fila.get("INTERMEDIO_REC", 0)),
        "carga_punta": a_num(fila.get("PUNTA_REC", 0)),
        "descarga_base": a_num(fila.get("BASE_ENT", 0)),
        "descarga_intermedio": a_num(fila.get("INTERMEDIO_ENT", 0)),
        "descarga_punta": a_num(fila.get("PUNTA_ENT", 0)),
    }
