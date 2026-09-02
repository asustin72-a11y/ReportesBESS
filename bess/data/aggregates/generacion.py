"""Consultas de energía de generación por periodo (sin dependencias de CFE/reports)."""

from __future__ import annotations

from pathlib import Path

import pandas as pd

from bess.config import rutas as rutas_mod
from bess.data.report_store import cargar_reporte, reporte_existe


def ruta_energia_generacion_por_dia(subestacion: str) -> Path:
    return rutas_mod.ruta_reporte(subestacion, f"ENERGIA_Generacion_{subestacion}_POR_DIA.csv")


def _sumar_diario_periodo(ruta: Path, fecha_inicio, fecha_fin) -> dict[str, float] | None:
    if not reporte_existe(ruta):
        return None
    df = cargar_reporte(ruta)
    if "FECHA" not in df.columns:
        return None
    df["FECHA_DT"] = pd.to_datetime(df["FECHA"], format="%d/%m/%Y", errors="coerce")
    mask = (df["FECHA_DT"].dt.date >= fecha_inicio) & (df["FECHA_DT"].dt.date <= fecha_fin)
    df_r = df[mask]
    resultado = {"base": 0.0, "intermedio": 0.0, "punta": 0.0}
    for col, clave in (
        ("BASE_REC", "base"),
        ("INTERMEDIO_REC", "intermedio"),
        ("PUNTA_REC", "punta"),
    ):
        if col in df_r.columns:
            resultado[clave] = float(pd.to_numeric(df_r[col], errors="coerce").fillna(0).sum())
    return resultado


def sumar_generacion_por_periodo(
    subestacion: str,
    fecha_inicio,
    fecha_fin,
) -> dict[str, float] | None:
    """Suma kWh de generación (BASE/INTERMEDIO/PUNTA) en un rango de fechas."""
    return _sumar_diario_periodo(
        ruta_energia_generacion_por_dia(subestacion), fecha_inicio, fecha_fin
    )


def sumar_generacion_medidor_por_periodo(
    subestacion: str,
    prefijo_medidor: str,
    fecha_inicio,
    fecha_fin,
) -> dict[str, float] | None:
    """Suma kWh de un medidor de generación (diario ENERGIA_{prefijo}_POR_DIA)."""
    return _sumar_diario_periodo(
        rutas_mod.ruta_energia_por_dia(prefijo_medidor, subestacion),
        fecha_inicio,
        fecha_fin,
    )


def fuente_energetica_medidor(nombre_medidor: str) -> tuple[str, str]:
    """(tipo, etiqueta): gas si el nombre sugiere cogeneración; si no, solar."""
    if "COGENER" in (nombre_medidor or "").upper():
        return "gas", "Cogeneración (gas)"
    return "solar", "Generación solar"
