"""Selección del Día Tipo (mar–jue con carga y descarga BESS) para el reporte acumulado."""

from __future__ import annotations

from datetime import date, timedelta

import pandas as pd

from bess.config.paths import ruta_energia_bess_por_dia
from bess.config.subestaciones import (
    etiqueta_medidor_consumo,
    medidor_consumo_por_prefijo,
    ruta_combinado_por_prefijo,
    subestacion_por_prefijo,
)
from bess.core.dates import rango_datetimes_operativo
from bess.core.numbers import kwh_para_calculo

_DIAS_LABORABLES = (1, 2, 3)  # martes, miércoles, jueves
_DIAS_ES = (
    "Lunes",
    "Martes",
    "Miércoles",
    "Jueves",
    "Viernes",
    "Sábado",
    "Domingo",
)
_MAX_DIAS_ATRAS = 180
_COLS_REC = ("BASE_REC", "INTERMEDIO_REC", "PUNTA_REC")
_COLS_ENT = ("BASE_ENT", "INTERMEDIO_ENT", "PUNTA_ENT")


def titulo_dia_tipo(prefijo: str) -> str:
    """Título: Día Tipo · {subestación} · {medidor facturación}."""
    sub = subestacion_por_prefijo(prefijo)
    med_et = etiqueta_medidor_consumo(prefijo)
    sub_nombre = sub.nombre.replace("Subestación ", "") if sub else prefijo
    return f"Día Tipo · {sub_nombre} · {med_et}"


def subestacion_tiene_granja_solar(sub) -> bool:
    return bool(sub and sub.granja_csv and sub.granja_bd)


def cargar_perfil_dia(prefijo: str, fecha: date) -> pd.DataFrame:
    ruta_combinado_p = ruta_combinado_por_prefijo(prefijo)
    if not ruta_combinado_p or not ruta_combinado_p.exists():
        return pd.DataFrame()
    df = pd.read_csv(ruta_combinado_p, encoding="utf-8-sig")
    df["DATETIME"] = pd.to_datetime(df["FECHA_HORA"], format="%d/%m/%Y %H:%M")
    inicio, fin = rango_datetimes_operativo(fecha, fecha)
    mask = (df["DATETIME"] >= inicio) & (df["DATETIME"] <= fin)
    return df.loc[mask].sort_values("DATETIME").reset_index(drop=True)


def _carga_descarga_fila(row) -> tuple[int, int]:
    carga = sum(kwh_para_calculo(row.get(c, 0)) for c in _COLS_REC)
    desc = sum(kwh_para_calculo(row.get(c, 0)) for c in _COLS_ENT)
    return carga, desc


def buscar_dia_tipo(prefijo: str, fecha_corte: date) -> dict | None:
    """
    Último mar/mié/jue anterior a fecha_corte con carga y descarga BESS.

    No está limitado al mes de corte.
    """
    ruta = ruta_energia_bess_por_dia(prefijo)
    if not ruta.exists():
        return None

    df = pd.read_csv(ruta)
    df["FECHA_DT"] = pd.to_datetime(df["FECHA"], format="%d/%m/%Y")
    por_fecha = {row["FECHA_DT"].date(): row for _, row in df.iterrows()}

    candidato = fecha_corte - timedelta(days=1)
    for _ in range(_MAX_DIAS_ATRAS):
        if candidato.weekday() in _DIAS_LABORABLES and candidato in por_fecha:
            carga, desc = _carga_descarga_fila(por_fecha[candidato])
            if carga > 0 and desc > 0 and not cargar_perfil_dia(prefijo, candidato).empty:
                med = medidor_consumo_por_prefijo(prefijo)
                sub = subestacion_por_prefijo(prefijo)
                return {
                    "fecha": candidato,
                    "fecha_str": candidato.strftime("%d/%m/%Y"),
                    "dia_semana": _DIAS_ES[candidato.weekday()],
                    "carga_kwh": carga,
                    "descarga_kwh": desc,
                    "prefijo": prefijo,
                    "medidor_etiqueta": etiqueta_medidor_consumo(prefijo),
                    "medidor_nombre": med.nombre if med else prefijo,
                    "incluye_granja": subestacion_tiene_granja_solar(sub),
                }
        candidato -= timedelta(days=1)
    return None
