"""Consultas de energía de generación por periodo (sin dependencias de CFE/reports)."""

from __future__ import annotations

from pathlib import Path

import pandas as pd

from bess.config import rutas as rutas_mod


def ruta_energia_generacion_por_dia(subestacion: str) -> Path:
    return rutas_mod.ruta_reporte(subestacion, f"ENERGIA_Generacion_{subestacion}_POR_DIA.csv")


def sumar_generacion_por_periodo(
    subestacion: str,
    fecha_inicio,
    fecha_fin,
) -> dict[str, float] | None:
    """Suma kWh de generación (BASE/INTERMEDIO/PUNTA) en un rango de fechas."""
    ruta = ruta_energia_generacion_por_dia(subestacion)
    if not ruta.exists():
        return None

    df = pd.read_csv(ruta, encoding="utf-8-sig")
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
