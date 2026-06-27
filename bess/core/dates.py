"""Utilidades de fechas para perfiles CSV."""

from __future__ import annotations

from datetime import datetime

import pandas as pd

from bess.core.console import log


def normalizar_fecha(fecha):
    """Convierte fecha al formato DD/MM/YYYY HH:MM."""
    if isinstance(fecha, str):
        return fecha
    return fecha.strftime("%d/%m/%Y %H:%M")


def validar_y_convertir_fecha(fecha_str):
    """Normaliza fechas de CSV al formato YYYY-MM-DD HH:MM:SS."""
    if isinstance(fecha_str, datetime):
        return fecha_str.strftime("%Y-%m-%d %H:%M:%S")

    fecha_str = str(fecha_str).strip()
    formatos_posibles = [
        "%Y-%m-%d %H:%M:%S",
        "%d/%m/%Y %H:%M:%S",
        "%d/%m/%Y %I:%M:%S %p",
        "%d/%m/%Y %I:%M:%S.%f %p",
        "%d/%m/%Y %I:%M:%S.%f",
        "%d/%m/%Y %I:%M %p",
        "%Y/%m/%d %H:%M:%S",
        "%Y-%m-%dT%H:%M:%S",
        "%Y-%m-%d %H:%M:%S.%f",
        "%d-%m-%Y %H:%M:%S",
        "%m/%d/%Y %H:%M:%S",
    ]

    fecha_limpia = fecha_str
    for old, new in (
        ("p. m.", "PM"), ("a. m.", "AM"), ("p. m", "PM"), ("a. m", "AM"),
        ("p.m.", "PM"), ("a.m.", "AM"), ("p.m", "PM"), ("a.m", "AM"),
    ):
        fecha_limpia = fecha_limpia.replace(old, new)

    for formato in formatos_posibles:
        try:
            return datetime.strptime(fecha_limpia, formato).strftime("%Y-%m-%d %H:%M:%S")
        except ValueError:
            continue

    try:
        return pd.to_datetime(fecha_str).strftime("%Y-%m-%d %H:%M:%S")
    except Exception:
        log(f"ADVERTENCIA: No se pudo convertir la fecha: {fecha_str}")
        return fecha_str
