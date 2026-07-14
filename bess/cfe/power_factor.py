"""Factor de potencia y cargo FP."""

from __future__ import annotations

from decimal import Decimal, ROUND_HALF_UP

from bess.core.numbers import a_num as _a_num, redondear_mxn_energia
from bess.cfe.energy_month import kwh_activo_tres_periodos

FP_UMBRAL_PCT = 97.0
FP_MAX_BONIFICACION = 0.025
FP_MAX_PENALIZACION = 1.20


def _coef_cargo_fp_redondeado(coef):
    return float(Decimal(str(coef)).quantize(Decimal("0.001"), rounding=ROUND_HALF_UP))


def calcular_factor_potencia_pct(kwh_activo, kvarh_total):
    kwh_activo = _a_num(kwh_activo)
    kvarh_total = _a_num(kvarh_total)
    if kwh_activo <= 0:
        return 0.0
    return round(kwh_activo / ((kwh_activo**2 + kvarh_total**2) ** 0.5) * 100, 2)


def calcular_factor_potencia_recibo(res_energia, kvarh_total):
    if kvarh_total is None:
        return None
    return calcular_factor_potencia_pct(
        kwh_activo_tres_periodos(res_energia), kvarh_total
    )


def calcular_cargo_fp(factor_potencia_pct, cargo_fijo, energia, capacidad):
    if factor_potencia_pct is None:
        return 0.0
    fp = _a_num(factor_potencia_pct)
    if fp <= 0:
        return 0.0
    base = _a_num(cargo_fijo) + _a_num(energia) + _a_num(capacidad)
    if fp < FP_UMBRAL_PCT:
        coef = min((3 / 5) * ((97 / fp) - 1), FP_MAX_PENALIZACION)
        coef = _coef_cargo_fp_redondeado(coef)
        return redondear_mxn_energia(coef * base)
    if fp > FP_UMBRAL_PCT:
        coef = min((1 / 4) * (1 - (97 / fp)), FP_MAX_BONIFICACION)
        coef = _coef_cargo_fp_redondeado(coef)
        return redondear_mxn_energia(-coef * base)
    return 0.0
