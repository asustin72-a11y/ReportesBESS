"""Costo de energía diario por periodo tarifario."""

from __future__ import annotations

import os
from datetime import datetime

from bess.config.subestaciones import ruta_energia_dia_por_prefijo
from bess.core.numbers import a_num, kwh_para_calculo, redondear_mxn_energia
from bess.cfe.daily_data import fila_por_fecha_csv
from bess.tariffs.loader import cargar_tarifas

_PERIODOS_ENERGIA_KEYS = ("base", "intermedio", "punta")
_COL_ENERGIA_CON = {
    "base": "BASE_REC",
    "intermedio": "INTERMEDIO_REC",
    "punta": "PUNTA_REC",
}
_COL_ENERGIA_SIN = {
    "base": "BASE_REC_SIN_BESS",
    "intermedio": "INTERMEDIO_REC_SIN_BESS",
    "punta": "PUNTA_REC_SIN_BESS",
}
_TARIFA_PERIODO = {"base": "Base", "intermedio": "Intermedio", "punta": "Punta"}


def calcular_costo_energia_dia(
    fecha_str: str,
    prefijo: str,
    con_bess: bool = True,
    tarifas: dict | None = None,
):
    """Costo de energía de un solo día: kWh redondeados × tarifa por periodo."""
    if tarifas is None:
        tarifas = cargar_tarifas()
    columnas = _COL_ENERGIA_CON if con_bess else _COL_ENERGIA_SIN
    ruta_p = ruta_energia_dia_por_prefijo(prefijo)
    if not ruta_p or not ruta_p.exists():
        return {k: 0.0 for k in _PERIODOS_ENERGIA_KEYS}
    ruta = str(ruta_p)
    fila = fila_por_fecha_csv(ruta, fecha_str)
    if fila is None:
        return None

    mes = datetime.strptime(fecha_str, "%d/%m/%Y").month
    por_periodo = {}
    for clave in _PERIODOS_ENERGIA_KEYS:
        col = columnas[clave]
        if col not in fila.index:
            return None
        kwh = kwh_para_calculo(a_num(fila.get(col, 0)))
        precio = tarifas.get(_TARIFA_PERIODO[clave], {}).get(mes, 0)
        por_periodo[clave] = {
            "kwh": kwh,
            "precio": precio,
            "costo_mxn": redondear_mxn_energia(kwh * precio),
        }
    total_mxn = redondear_mxn_energia(sum(p["costo_mxn"] for p in por_periodo.values()))
    return {
        "por_periodo": por_periodo,
        "total_kwh": sum(p["kwh"] for p in por_periodo.values()),
        "total_mxn": total_mxn,
    }
