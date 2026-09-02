"""Lectura de agregados diarios desde reportes (BD preferente / CSV fallback)."""

from __future__ import annotations

import pandas as pd

from bess.config.paths import ruta_energia_bess_por_dia
from bess.config.subestaciones import ruta_energia_dia_por_prefijo
from bess.core.numbers import a_num
from bess.data.report_store import cargar_reporte, columnas_reporte, reporte_existe


def fila_por_fecha_csv(ruta: str, fecha_str: str):
    if not reporte_existe(ruta):
        return None
    df = cargar_reporte(ruta)
    if df.empty or "FECHA" not in df.columns:
        return None
    fila = df[df["FECHA"] == fecha_str]
    return fila.iloc[0] if len(fila) > 0 else None


def energia_diaria_tiene_sin_bess(prefijo: str) -> bool:
    ruta_p = ruta_energia_dia_por_prefijo(prefijo)
    if not ruta_p or not reporte_existe(ruta_p):
        return False
    cols = columnas_reporte(ruta_p) or []
    return "BASE_REC_SIN_BESS" in cols


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
