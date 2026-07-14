"""Formateo numérico y reglas de redondeo CFE/BESS."""

from __future__ import annotations

from decimal import ROUND_HALF_UP, Decimal

import numpy as np
import pandas as pd


def a_num(val) -> float:
    v = pd.to_numeric(val, errors="coerce")
    return 0.0 if pd.isna(v) else float(v)


def sumar_energia(val) -> float:
    """Suma kWh conservando decimales."""
    if isinstance(val, pd.Series):
        return float(pd.to_numeric(val, errors="coerce").fillna(0).sum())
    if isinstance(val, pd.DataFrame):
        return float(pd.to_numeric(val, errors="coerce").fillna(0).sum().sum())
    if isinstance(val, (list, tuple, np.ndarray)):
        return float(np.nansum(pd.to_numeric(val, errors="coerce")))
    return a_num(val)


def _redondear_half_up(val, decimales: int = 0):
    quantum = Decimal("1") if decimales == 0 else Decimal(f'0.{"0" * (decimales - 1)}1')
    return Decimal(str(a_num(val))).quantize(quantum, rounding=ROUND_HALF_UP)


def redondear_kwh(val) -> int:
    """kWh: redondeo al entero más cercano (≥0.5 arriba, <0.5 abajo)."""
    return int(_redondear_half_up(val, 0))


def fmt_kwh(val) -> str:
    return f"{redondear_kwh(val):,}"


def redondear_mxn_energia(val) -> float:
    return float(_redondear_half_up(val, 2))


def kwh_para_calculo(val) -> int:
    return redondear_kwh(val)


def redondear_arriba_kw(val) -> int:
    return int(np.ceil(a_num(val)))


def redondear_arriba_mxn(val) -> float:
    return np.ceil(a_num(val) * 100) / 100
