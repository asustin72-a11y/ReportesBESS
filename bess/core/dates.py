"""Utilidades de fechas para perfiles CSV."""

from __future__ import annotations

from datetime import date, datetime, time, timedelta

import pandas as pd

from bess.core.console import log

_FMT_FECHA = "%d/%m/%Y"
_FMT_FECHA_HORA = "%d/%m/%Y %H:%M"
_INICIO_DIA_OPERATIVO = time(0, 5)
_FIN_DIA_OPERATIVO = time(0, 0)


def normalizar_fecha(fecha):
    """Convierte fecha al formato DD/MM/YYYY HH:MM:SS."""
    if isinstance(fecha, str):
        return fecha
    return fecha.strftime("%d/%m/%Y %H:%M:%S")


def validar_y_convertir_fecha(fecha_str):
    """Normaliza fechas de CSV al formato YYYY-MM-DD HH:MM:SS."""
    if isinstance(fecha_str, datetime):
        return fecha_str.strftime("%Y-%m-%d %H:%M:%S")

    fecha_str = str(fecha_str).strip()
    formatos_posibles = [
        "%Y-%m-%d %H:%M:%S",
        "%d/%m/%Y %H:%M:%S",
        "%d/%m/%Y %H:%M",
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
        return pd.to_datetime(fecha_str, dayfirst=True).strftime("%Y-%m-%d %H:%M:%S")
    except Exception:
        log(f"ADVERTENCIA: No se pudo convertir la fecha: {fecha_str}")
        return fecha_str


def fecha_operativa(dt: datetime) -> date:
    """Día operativo: de 00:05 del día D hasta 00:00 del día D+1 (inclusive)."""
    if dt.hour == 0 and dt.minute < 5:
        return (dt - timedelta(days=1)).date()
    return dt.date()


def fecha_operativa_desde_str(fecha_hora: str) -> date:
    texto = str(fecha_hora).strip()
    for formato in (_FMT_FECHA_HORA, "%d/%m/%Y %H:%M:%S", "%Y-%m-%d %H:%M:%S"):
        try:
            return fecha_operativa(datetime.strptime(texto, formato))
        except ValueError:
            continue
    dt = datetime.strptime(validar_y_convertir_fecha(texto), "%Y-%m-%d %H:%M:%S")
    return fecha_operativa(dt)


def fecha_operativa_como_str(fecha_hora: str) -> str:
    return fecha_operativa_desde_str(fecha_hora).strftime(_FMT_FECHA)


def rango_datetimes_operativo(fecha_inicio: date, fecha_fin: date) -> tuple[datetime, datetime]:
    inicio = datetime.combine(fecha_inicio, _INICIO_DIA_OPERATIVO)
    fin = datetime.combine(fecha_fin + timedelta(days=1), _FIN_DIA_OPERATIVO)
    return inicio, fin


def etiqueta_rango_operativo(fecha_inicio: date, fecha_fin: date) -> str:
    if fecha_inicio == fecha_fin:
        return f"{fecha_inicio.strftime(_FMT_FECHA)} (00:05 – 00:00)"
    return (
        f"{fecha_inicio.strftime(_FMT_FECHA)} al {fecha_fin.strftime(_FMT_FECHA)} "
        "(día operativo 00:05–00:00)"
    )


def serie_fecha_operativa(dt: pd.Series) -> pd.Series:
    """Series datetime → date operativo (vectorizado)."""
    fechas = dt.dt.floor("D")
    ajustar = (dt.dt.hour == 0) & (dt.dt.minute < 5)
    return fechas.where(~ajustar, fechas - pd.Timedelta(days=1)).dt.date


def agregar_fecha_operativa(
    df: pd.DataFrame,
    *,
    col_datetime: str = "DATETIME",
    col_fecha_hora: str | None = "FECHA_HORA",
    out_col: str = "FECHA",
) -> pd.DataFrame:
    out = df.copy()
    if col_datetime not in out.columns:
        if col_fecha_hora and col_fecha_hora in out.columns:
            normalizada = out[col_fecha_hora].map(validar_y_convertir_fecha)
            out[col_datetime] = pd.to_datetime(normalizada, errors="coerce")
        else:
            raise KeyError(f"Falta columna {col_datetime} o {col_fecha_hora}")
    out[out_col] = pd.to_datetime(serie_fecha_operativa(out[col_datetime])).dt.strftime(_FMT_FECHA)
    return out


def mascara_rango_operativo(
    df: pd.DataFrame,
    fecha_inicio: date,
    fecha_fin: date,
    *,
    col_datetime: str = "DATETIME",
) -> pd.Series:
    inicio, fin = rango_datetimes_operativo(fecha_inicio, fecha_fin)
    return (df[col_datetime] >= inicio) & (df[col_datetime] <= fin)
