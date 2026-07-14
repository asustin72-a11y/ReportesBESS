"""Pruebas de bess/cfe/power_factor.py: factor de potencia y cargo FP.

calcular_cargo_fp aplica un cargo (penalizacion) o bonificacion sobre el
recibo segun que tan lejos este el factor de potencia del umbral de 97%,
con topes en ambos sentidos. Los umbrales y topes son valores de negocio
exactos (97.0%, tope de penalizacion 120%): un error de "<" vs "<=" en
el limite cambia el cobro de todo un mes. Valores esperados tomados de
la implementacion real.
"""

from __future__ import annotations

import pytest

from bess.cfe.power_factor import (
    FP_MAX_PENALIZACION,
    FP_UMBRAL_PCT,
    calcular_cargo_fp,
    calcular_factor_potencia_pct,
)


def test_factor_potencia_pct_casos_extremos():
    assert calcular_factor_potencia_pct(0, 100) == 0.0
    assert calcular_factor_potencia_pct(100, 0) == 100.0
    assert calcular_factor_potencia_pct(100, 100) == pytest.approx(70.71, abs=0.01)


def test_cargo_fp_sin_dato_no_cobra():
    assert calcular_cargo_fp(None, 100, 500, 400) == 0.0
    assert calcular_cargo_fp(0, 100, 500, 400) == 0.0


def test_cargo_fp_en_el_umbral_exacto_no_cobra_ni_bonifica():
    # FP == 97.0 exacto: ni penalizacion ni bonificacion (la funcion solo
    # actua en < umbral o > umbral, nunca en el punto exacto).
    assert FP_UMBRAL_PCT == 97.0
    assert calcular_cargo_fp(97.0, 100, 500, 400) == 0.0


def test_cargo_fp_penaliza_bajo_el_umbral():
    base = 100 + 500 + 400  # cargo_fijo + energia + capacidad = 1000
    cargo_96 = calcular_cargo_fp(96.0, 100, 500, 400)
    cargo_90 = calcular_cargo_fp(90.0, 100, 500, 400)
    assert cargo_96 > 0
    assert cargo_90 > 0
    # a menor FP, mayor penalizacion
    assert cargo_90 > cargo_96
    assert cargo_96 == pytest.approx(6.0)
    assert cargo_90 == pytest.approx(47.0)
    assert base == 1000


def test_cargo_fp_respeta_el_tope_de_penalizacion():
    # Con FP muy bajo, el coeficiente teorico supera FP_MAX_PENALIZACION
    # (120%) y debe quedar topado ahi, no seguir creciendo.
    cargo_20 = calcular_cargo_fp(20.0, 100, 500, 400)
    cargo_10 = calcular_cargo_fp(10.0, 100, 500, 400)
    tope_esperado = FP_MAX_PENALIZACION * 1000  # 1200.0
    assert cargo_20 == cargo_10 == pytest.approx(tope_esperado)


def test_cargo_fp_bonifica_sobre_el_umbral():
    # Sobre 97%, el cargo es negativo (bonificacion / descuento).
    cargo_98 = calcular_cargo_fp(98.0, 100, 500, 400)
    cargo_100 = calcular_cargo_fp(100.0, 100, 500, 400)
    assert cargo_98 < 0
    assert cargo_100 < 0
    # a mayor FP, mayor bonificacion (mas negativo)
    assert cargo_100 < cargo_98
